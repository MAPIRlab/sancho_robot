import rclpy
import time
import json
import numpy as np
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from concurrent.futures import ThreadPoolExecutor
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from sancho_interfaces.msg import FaceDetectionArray, FaceDetection, FaceRecognitionArray, FaceRecognition
from sancho_interfaces.msg import FacePosition
from sancho_interfaces.srv import Training, GetString, Detection, Recognition
from std_srvs.srv import SetBool, Empty as EmptySrv

# --- Importamos nuestros nuevos módulos ---
from sancho_vision.nodes.face_engine import FaceEngine
from sancho_vision.nodes.smart_cache import SmartRecognitionCache
from sancho_vision.aligners.aligner_dlib import align_face # Utilizado en el API de ROS

LOWER_BOUND = 0.70
UPPER_BOUND = 0.90

class BodyFaceFusionNode(Node):
    def __init__(self):
        super().__init__('body_face_fusion_node')
        self.bridge = CvBridge()

        self.declare_parameters(namespace='', parameters=[
            ('human_tracking_topic',    '/sancho_perception/human_tracking'),
            ('face_recognitions_topic', '/face_recognitions'),
            ('detector_name',           'mtcnn'),   
            ('encoder_name',            'efficientface'),
            ('head_fraction',           0.40),   
            ('cache_ttl',               15.0),   
            ('cache_max_size',          20),      
            ('cleanup_timeout',         30.0),
            ('no_face_cooldown_sec',       2.0),
            ('no_face_movement_threshold', 20.0),
            ('reid_interval_sec',          3.0),
        ])

        self.head_fraction = float(self.get_parameter('head_fraction').value)
        self.cleanup_timeout = float(self.get_parameter('cleanup_timeout').value)

        # Iniciar Módulos Aislados
        self.engine = FaceEngine(
            self.get_parameter('detector_name').value,
            self.get_parameter('encoder_name').value
        )
        
        self.cache = SmartRecognitionCache(
            ttl=float(self.get_parameter('cache_ttl').value),
            max_size=int(self.get_parameter('cache_max_size').value),
            cooldown_sec=float(self.get_parameter('no_face_cooldown_sec').value),
            move_thresh=float(self.get_parameter('no_face_movement_threshold').value),
            reid_interval=float(self.get_parameter('reid_interval_sec').value),
            lower_bound=LOWER_BOUND
        )

        self.inference_pool = ThreadPoolExecutor(max_workers=1)

        # Configurar ROS 2
        human_topic = self.get_parameter('human_tracking_topic').value
        recog_topic = self.get_parameter('face_recognitions_topic').value
        
        self.sub_human = self.create_subscription(FaceDetectionArray, human_topic, self.human_callback, 10)
        self.pub_recog = self.create_publisher(FaceRecognitionArray, recog_topic, 5)

        self.training_srv = self.create_service(Training, "/recognition/training", self.training_service)
        self.get_faceprint_srv = self.create_service(GetString, "/recognition/get_faceprint", self.get_people_service)
        self.clear_no_name_srv = self.create_service(EmptySrv, "/recognition/clear_no_name", self.clear_no_name_service)
        self.set_learn_without_name_srv = self.create_service(SetBool, "/recognition/set_learn_without_name", self.set_learn_without_name_service)
        self.detect_srv = self.create_service(Detection, "detection", self.detect_faces_service)
        self.recognize_srv = self.create_service(Recognition, "recognition", self.recognize_face_service)

        self.training_dispatcher = {
            "refine_class": self.engine.classifier.refine_class,
            "add_features": self.engine.classifier.add_features,
            "add_class":    self.engine.classifier.add_class,
            "rename_class": self.engine.classifier.rename_class,
            "delete_class": self.engine.classifier.delete_class,
            "delete_all":   self.engine.classifier.delete_all
        }

        self.maintenance_timer = self.create_timer(5.0, lambda: self.cache.prune_and_cleanup(time.monotonic(), self.cleanup_timeout))
        self.get_logger().info("BodyFaceFusionNode (Modular) Iniciado.")

    def _build_ros_msg(self, entry: dict, header) -> FaceRecognition:
        recog = FaceRecognition()
        if not entry or entry.get('processing', False) or entry.get('no_face', False):
            recog.classified_id = ''
            recog.classified_name = 'Unknown'
            recog.distance = 0.0
            recog.face_aligned = Image(header=header, encoding="bgr8")
            return recog

        faceprint = entry['faceprint']
        recog.classified_id = faceprint.get('id', '')
        recog.classified_name = faceprint.get('name', 'Unknown')
        recog.distance = float(entry.get('distance', 0.0))
        recog.features = [float(f) for f in entry.get('features', [])]
        if entry.get('pos'): recog.pos = entry['pos']
        recog.face_updated = bool(entry.get('face_updated', False))

        if entry.get('face_aligned') is not None:
            recog.face_aligned = self.bridge.cv2_to_imgmsg(entry['face_aligned'], encoding="bgr8")
            recog.face_aligned.header = header
        else:
            recog.face_aligned = Image(header=header, encoding="bgr8")
        return recog

    def human_callback(self, msg: FaceDetectionArray):
        if not msg.detections: return
        try: frame = self.bridge.imgmsg_to_cv2(msg.image, "bgr8")
        except: return

        out_msg = FaceRecognitionArray(header=msg.header)
        out_msg.image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
        out_msg.image.header = msg.header

        now = time.monotonic()
        for body in msg.detections:
            action, cached_entry = self.cache.get_action_and_entry(body.tid, body.corner.x, body.corner.y, now)

            if action == 'TRIGGER':
                self.get_logger().info(f"[TID {body.tid}] Enviando a motor de inferencia...")
                self.cache.mark_processing(body.tid, body.corner.x, body.corner.y, now)
                self.inference_pool.submit(self._inference_worker, body.tid, frame.copy(), body)

            out_msg.recognitions.append(self._build_ros_msg(cached_entry, msg.header))
            out_msg.detections.append(body)

        self.pub_recog.publish(out_msg)

    def _inference_worker(self, tid: int, frame: np.ndarray, body: FaceDetection):
        try:
            x, y = int(body.corner.x), int(body.corner.y)
            w, h = int(body.width), int(body.height)
            
            result = self.engine.process_body_crop(frame, x, y, w, h, self.head_fraction)
            
            if result is None:
                self.cache.commit_no_face(tid)
            else:
                self.cache.commit_result(tid, result)
        except Exception as e:
            import traceback
            self.get_logger().error(f"[TID {tid}] Error en Hilo IA: {e}\n{traceback.format_exc()}")
            self.cache.abort_inference(tid)

    def training_service(self, request, response):
        try:
            cmd_type = request.cmd_type.data
            args = json.loads(request.args.data)
            target_tid = args.pop("tid", None)

            if cmd_type in self.training_dispatcher:
                result, message = self.training_dispatcher[cmd_type](**args)
                if result >= 0 and target_tid is not None:
                    face_id = message.get("id") if isinstance(message, dict) else None
                    self.cache.force_training_update(target_tid, args.get("class_name", args.get("name")), face_id)
            else:
                result, message = -1, f"Unknown command: {cmd_type}"
        except Exception as e:
            result, message = -1, f"Error: {e}"

        response.result = result
        response.message.data = str(message["id"] if cmd_type == "add_class" and result >= 0 else message)
        return response

    # ── APIs externas de Detección/Reconocimiento (Uso directo del Engine) ──
    def detect_faces_service(self, request, response):
        try:
            frame = self.bridge.imgmsg_to_cv2(request.frame, "bgr8")
            positions, confidences = self.engine.detector.get_faces(frame)
            out_positions, out_scores = [], []
            for pos, conf in zip(positions, confidences):
                fp = FacePosition()
                if hasattr(pos, 'left'): fp.x, fp.y, fp.width, fp.height = float(pos.left()), float(pos.top()), float(pos.width()), float(pos.height())
                else: fp.x, fp.y, fp.width, fp.height = map(float, pos)
                out_positions.append(fp)
                out_scores.append(float(conf))
            response.positions, response.scores = out_positions, out_scores
            return response
        except Exception as e:
            return response

    def recognize_face_service(self, request, response):
        try:
            frame = self.bridge.imgmsg_to_cv2(request.frame, "bgr8")
            pos_req = [int(request.position.x), int(request.position.y), int(request.position.width), int(request.position.height)]
            
            face_aligned = align_face(frame, pos_req)
            features = self.engine.encoder.encode_face(face_aligned)
            faceprint, distance, pos = self.engine.classifier.classify_face(features)
            
            if distance >= UPPER_BOUND and request.score >= 1.0:
                self.engine.classifier.refine_class(faceprint['id'], features, pos)
                face_updated = self.engine.classifier.save_face(faceprint['id'], face_aligned, request.score)
            else: face_updated = False
                
            response.face_aligned = self.bridge.cv2_to_imgmsg(face_aligned, encoding="bgr8")
            response.features = [float(f) for f in features]
            response.classified_id = str(faceprint.get('id', ''))
            response.classified_name = str(faceprint.get('name', 'Unknown'))
            response.distance = float(distance)
            response.pos = int(pos) if pos is not None else -1 
            response.face_updated = bool(face_updated)
            return response
        except Exception as e:
            return response

    def get_people_service(self, request, response):
        args = json.loads(request.args) if request.args else {}
        if args.get("id"): result = self.engine.classifier.db.get_by_id(args["id"])
        else: result = self.engine.classifier.db.get_all(args.get("name", ""))
        response.text = json.dumps(result)
        return response

    def clear_no_name_service(self, request, response):
        self.engine.classifier.clear_no_name()
        return response

    def set_learn_without_name_service(self, request, response):
        return response

def main(args=None):
    rclpy.init(args=args)
    node = BodyFaceFusionNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try: executor.spin()
    except KeyboardInterrupt: pass
    finally:
        node.inference_pool.shutdown(wait=False)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__': main()