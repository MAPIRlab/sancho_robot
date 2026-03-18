import cv2
import rclpy
import time
import threading
import numpy as np
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from concurrent.futures import ThreadPoolExecutor
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from sancho_interfaces.msg import FaceDetectionArray, FaceDetection, FaceRecognitionArray, FaceRecognition
from geometry_msgs.msg import Point

from sancho_vision.detectors import load_detector
from sancho_vision.encoders import load_encoder
from sancho_vision.classifiers.complex_classifier import ComplexClassifier
from sancho_vision.aligners.aligner_dlib import align_face

from sancho_interfaces.srv import Training, GetString
from sancho_interfaces.srv import Detection, Recognition
from std_srvs.srv import SetBool, Empty as EmptySrv

from sancho_interfaces.msg import FacePosition
import json

# ──────────────────────────────────────────────────────────
#  Threshold tiers (mirrors HumanFaceRecognizerLifecycleNode)
# ──────────────────────────────────────────────────────────
LOWER_BOUND  = 0.70   # below  → Unknown
MIDDLE_BOUND = 0.80   # 0.75–0.80 → probable
UPPER_BOUND  = 0.90   # ≥ 0.90  → very confident → refine online


class BodyFaceFusionNode(Node):
    def __init__(self):
        super().__init__('body_face_fusion_node')
        self.bridge = CvBridge()

        # ── Parámetros Actualizados ─────────────────────────────────────────
        self.declare_parameters(namespace='', parameters=[
            ('human_tracking_topic',    '/sancho_perception/human_tracking'),
            ('face_recognitions_topic', '/face_recognitions'),
            ('detector_name',           'mtcnn'),   
            ('encoder_name',            'efficientface'),
            ('head_fraction',           0.40),   
            ('cache_ttl',               15.0),   
            ('cache_max_size',          20),      
            ('cleanup_timeout',         30.0),   
        ])

        detector_name  = self.get_parameter('detector_name').value
        encoder_name   = self.get_parameter('encoder_name').value
        self.cache_ttl      = float(self.get_parameter('cache_ttl').value)
        self.cache_max_size = int(self.get_parameter('cache_max_size').value)
        self.head_fraction  = float(self.get_parameter('head_fraction').value)
        self.cleanup_timeout = float(self.get_parameter('cleanup_timeout').value)

        # ── Componentes ML ─────────────────────────────────────────────────
        try:
            self.detector = load_detector(detector_name)
            self.get_logger().info(f"Detector cargado: {detector_name}")
        except Exception as e:
            self.get_logger().error(f"Error al cargar detector: {e}")
            raise

        try:
            self.encoder = load_encoder(encoder_name)
            self.get_logger().info(f"Encoder cargado: {encoder_name} (EfficientFaceV2S)")
        except Exception as e:
            self.get_logger().error(f"Error al cargar encoder: {e}")
            raise

        # El clasificador gestiona el archivo JSON 'faceprints_db.json'
        self.classifier = ComplexClassifier('save')

        # ── Control de Flujo y Estados ──────────────────────────────────────
        self.identifying_tids = set()
        self.pending_confirmation = set()
        self.pending_naming = set()  # TIDs esperando respuesta del usuario
        self.recognition_cache = {}  # tid -> {faceprint, distance, features, etc.}
        self.last_seen = {}          # tid -> timestamp (para cleanup)
        self.retry_count = {}        # tid -> int (para rate-limit de inferencia)
        
        self.state_lock = threading.Lock()
        
        # Pool de hilos para no bloquear el callback de ROS con la red neuronal
        self.inference_pool = ThreadPoolExecutor(max_workers=1)

        # ── Servidores de Servicios ────────────────────────────────────────
        self.training_srv = self.create_service(Training, "/recognition/training", self.training_service)
        self.get_faceprint_srv = self.create_service(GetString, "/recognition/get_faceprint", self.get_people_service)
        self.clear_no_name_srv = self.create_service(EmptySrv, "/recognition/clear_no_name", self.clear_no_name_service)
        self.set_learn_without_name_srv = self.create_service(SetBool, "/recognition/set_learn_without_name", self.set_learn_without_name_service)
        self.detect_srv = self.create_service(Detection, "detection", self.detect_faces_service)
        self.recognize_srv = self.create_service(Recognition, "recognition", self.recognize_face_service)
        
        # Mapeo de comandos para el dispatcher del clasificador
        self.training_dispatcher = {
            "refine_class": self.classifier.refine_class,
            "add_features": self.classifier.add_features,
            "add_class":    self.classifier.add_class,
            "rename_class": self.classifier.rename_class,
            "delete_class": self.classifier.delete_class,
            "delete_all":   self.classifier.delete_all
        }

        # ── ROS I/O ────────────────────────────────────────────────────────
        human_topic = self.get_parameter('human_tracking_topic').value
        recog_topic = self.get_parameter('face_recognitions_topic').value
        
        self.sub_human = self.create_subscription(
            FaceDetectionArray, human_topic, self.human_callback, 10)
        
        self.pub_recog = self.create_publisher(
            FaceRecognitionArray, recog_topic, 5)

        # ── Timers de Mantenimiento ────────────────────────────────────────
        self.cache_prune_timer = self.create_timer(5.0, self.prune_cache)
        self.cleanup_timer     = self.create_timer(10.0, self.cleanup_body_tracks)

        self.get_logger().info(
            f"BodyFaceFusionNode Iniciado | "
            f"Encoder: {encoder_name} | "
            f"Cache TTL: {self.cache_ttl}s"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Identification pipeline
    # ─────────────────────────────────────────────────────────────────────────
    def _update_recognition_entry(self, tid, face_aligned, features, faceprint, distance, pos):
        """Helper to update or create a recognition entry in the cache."""
        self.recognition_cache[tid] = {
            'face_aligned': face_aligned,
            'features':     features,
            'faceprint':    faceprint,
            'distance':     distance,
            'pos':          pos,
            'face_updated': False,
            'last_seen':    time.monotonic()
        }

    def human_callback(self, msg: FaceDetectionArray):
        if not msg.detections:
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg.image, "bgr8")
        except Exception as e:
            self.get_logger().error(f"CV Bridge error: {e}")
            return

        now = time.monotonic()
        out_msg = FaceRecognitionArray()
        out_msg.header = msg.header
        out_msg.image = self.bridge.cv2_to_imgmsg(frame, "bgr8")
        out_msg.image.header = msg.header

        with self.state_lock:
            for body in msg.detections:
                tid = body.tid
                self.last_seen[tid] = now

                # 1. ESTADO: Pendiente de nombre
                if tid in self.pending_naming:
                    if tid in self.recognition_cache:
                        entry = self.recognition_cache[tid]
                        entry['last_seen'] = now
                        recog = self._entry_to_recognition(entry)
                        recog.classified_name = 'Unknown'
                    else:
                        recog = self._create_unknown_placeholder(msg.header)
                        
                    out_msg.recognitions.append(recog)
                    out_msg.detections.append(body)
                    continue

                # 2. ESTADO: Pendiente de confirmación
                if tid in self.pending_confirmation:
                    if tid in self.recognition_cache:
                        entry = self.recognition_cache[tid]
                        entry['last_seen'] = now
                        recog = self._entry_to_recognition(entry)
                    else:
                        recog = self._create_unknown_placeholder(msg.header)
                        
                    out_msg.recognitions.append(recog)
                    out_msg.detections.append(body)
                    continue

                # 3. ESTADO: IA pensando
                if tid in self.identifying_tids:
                    recog = self._create_unknown_placeholder(msg.header)
                    out_msg.recognitions.append(recog)
                    out_msg.detections.append(body)
                    continue 

                # 4. ESTADO: Reconocido (Caché)
                if tid in self.recognition_cache:
                    entry = self.recognition_cache[tid]
                    entry['last_seen'] = now
                    recog = self._entry_to_recognition(entry)
                    recog.face_aligned.header = msg.header 
                    out_msg.recognitions.append(recog)
                    out_msg.detections.append(body)
                    continue

                # 5. ESTADO: Nuevo track -> IA
                if tid not in self.retry_count:
                    self.retry_count[tid] = 0

                if self.retry_count[tid] % 5 == 0:
                    self.get_logger().info(f"[TID {tid}] Enviando a IA...")
                    self.identifying_tids.add(tid) 
                    self.inference_pool.submit(
                        self.process_identification,
                        tid, frame.copy(), body 
                    )

                self.retry_count[tid] += 1
                
                recog = self._create_unknown_placeholder(msg.header)
                out_msg.recognitions.append(recog)
                out_msg.detections.append(body)

        self.pub_recog.publish(out_msg)

    def _create_unknown_placeholder(self, header):
        """Helper para crear el mensaje de desconocido."""
        recog = FaceRecognition()
        recog.classified_id = ''
        recog.classified_name = 'Analyzing...'
        recog.distance = 0.0
        recog.face_aligned = Image()
        recog.face_aligned.header = header
        recog.face_aligned.encoding = "bgr8"
        return recog

    def process_identification(self, tid: int, frame_raw: np.ndarray, body_det):
        self.get_logger().info(f"--- [HILO IA] Iniciando proceso para TID {tid} ---")
        
        try:
            x = int(body_det.corner.x)
            y = int(body_det.corner.y)
            w = int(body_det.width)
            h = int(body_det.height)

            y_margin = int(h * 0.2)
            x_margin = int(w * 0.2)
            head_h = int(h * self.head_fraction)

            y1 = max(0, y - y_margin)
            y2 = min(frame_raw.shape[0], y + head_h)
            x1 = max(0, x - x_margin)
            x2 = min(frame_raw.shape[1], x + w + x_margin)

            crop = frame_raw[y1:y2, x1:x2]

            if crop.shape[0] < 40 or crop.shape[1] < 40:
                self.get_logger().warn(f"[TID {tid}] Recorte demasiado pequeño: {crop.shape}")
                return

            positions, confidences = self.detector.get_faces(crop)

            if len(positions) == 0:
                self.get_logger().info(f"[TID {tid}] No se detectó cara.")
                return

            best_idx = int(np.argmax(confidences))
            best_conf = float(confidences[best_idx])

            if best_conf < 0.85:
                self.get_logger().warn(f"[TID {tid}] Baja confianza: {best_conf:.2f}")
                return

            best_face = positions[best_idx]
            if hasattr(best_face, 'left'): # Dlib
                face_x, face_y = best_face.left() + x1, best_face.top() + y1
                face_w, face_h = best_face.width(), best_face.height()
            else: # List/Array
                face_x, face_y = best_face[0] + x1, best_face[1] + y1
                face_w, face_h = best_face[2], best_face[3]
            
            absolute_position = [face_x, face_y, face_w, face_h]

            face_aligned = align_face(frame_raw, absolute_position)
            if face_aligned is None:
                return

            features = self.encoder.encode_face(face_aligned)
            faceprint, distance, pos = self.classifier.classify_face(features)
            display_name = faceprint.get("name", "Unknown") if isinstance(faceprint, dict) else "Unknown"

            with self.state_lock:
                if distance < LOWER_BOUND:
                    if tid not in self.pending_naming:
                        self.get_logger().warn(f"TID {tid} desconocido (dist: {distance:.2f}).")
                        self._update_recognition_entry(tid, face_aligned, features, 
                                                     {'id': '', 'name': 'Unknown'}, distance, pos)
                        self.pending_naming.add(tid)
                        
                elif distance < UPPER_BOUND:
                    if tid not in self.pending_confirmation:
                        self.get_logger().info(f"[TID {tid}] Dudoso. ¿Es '{display_name}'? (dist: {distance:.2f})")
                        self._update_recognition_entry(tid, face_aligned, features, faceprint, distance, pos)
                        self.pending_confirmation.add(tid)

                else:
                    self.get_logger().info(f"[TID {tid}] RECONOCIDO como '{display_name}' (dist: {distance:.2f})")
                    self._update_recognition_entry(tid, face_aligned, features, faceprint, distance, pos)

        except Exception as e:
            import traceback
            self.get_logger().error(f"[TID {tid}] ERROR EN IA: {e}\n{traceback.format_exc()}")
        
        finally:
            with self.state_lock:
                if tid in self.identifying_tids:
                    self.identifying_tids.remove(tid)

    def prune_cache(self):
        """Evict stale entries from the recognition cache (TTL + LRU)."""
        now = time.monotonic()
        with self.state_lock:
            expired = [
                tid for tid, e in self.recognition_cache.items()
                if (now - e.get('last_seen', 0)) > self.cache_ttl
            ]
            for tid in expired:
                del self.recognition_cache[tid]
                self.get_logger().info(f"[cache] Evicted TID {tid} (TTL expired)")

            if len(self.recognition_cache) > self.cache_max_size:
                sorted_ids = sorted(
                    self.recognition_cache.items(),
                    key=lambda kv: kv[1].get('last_seen', 0)
                )
                for tid, _ in sorted_ids[:len(self.recognition_cache) - self.cache_max_size]:
                    if tid in self.recognition_cache:
                        del self.recognition_cache[tid]
                        self.get_logger().info(f"[cache] Evicted TID {tid} (LRU)")

    def cleanup_body_tracks(self):
        """Remove tracking state for body TIDs that have disappeared."""
        now = time.monotonic()
        with self.state_lock:
            to_remove = [
                tid for tid, last in self.last_seen.items()
                if (now - last) > self.cleanup_timeout
            ]
            for tid in to_remove:
                self.last_seen.pop(tid, None)
                self.retry_count.pop(tid, None)
                self.recognition_cache.pop(tid, None)
                self.pending_naming.discard(tid)
                self.pending_confirmation.discard(tid)
                self.identifying_tids.discard(tid)
                self.get_logger().info(f"[body] Cleaned up TID {tid} (body track gone)")

    # ─────────────────────────────────────────────────────────────────────────
    #  Services
    # ─────────────────────────────────────────────────────────────────────────
    def detect_faces_service(self, request, response):
        try:
            frame = self.bridge.imgmsg_to_cv2(request.frame, "bgr8")
            positions, confidences = self.detector.get_faces(frame)
            
            out_positions = []
            out_scores = []
            
            for pos, conf in zip(positions, confidences):
                fp = FacePosition()
                if hasattr(pos, 'left'):
                    fp.x, fp.y = float(pos.left()), float(pos.top())
                    fp.width, fp.height = float(pos.width()), float(pos.height())
                else:
                    fp.x, fp.y, fp.width, fp.height = map(float, pos)
                
                out_positions.append(fp)
                out_scores.append(float(conf))
                
            response.positions = out_positions
            response.scores = out_scores
            return response
        except Exception as e:
            self.get_logger().error(f"API Detection service failed: {e}")
            return response

    def recognize_face_service(self, request, response):
        try:
            frame = self.bridge.imgmsg_to_cv2(request.frame, "bgr8")
            pos_req = [int(request.position.x), int(request.position.y), 
                       int(request.position.width), int(request.position.height)]
            
            face_aligned = align_face(frame, pos_req)
            features = self.encoder.encode_face(face_aligned)
            faceprint, distance, pos = self.classifier.classify_face(features)
            
            face_updated = False
            if distance >= UPPER_BOUND and request.score >= 1.0:
                self.classifier.refine_class(faceprint['id'], features, pos)
                face_updated = self.classifier.save_face(faceprint['id'], face_aligned, request.score)
                
            response.face_aligned = self.bridge.cv2_to_imgmsg(face_aligned, encoding="bgr8")
            response.features = [float(f) for f in features]
            response.classified_id = str(faceprint.get('id', ''))
            response.classified_name = str(faceprint.get('name', 'Unknown'))
            response.distance = float(distance)
            response.pos = int(pos) if pos is not None else -1 
            response.face_updated = bool(face_updated)
            return response
        except Exception as e:
            self.get_logger().error(f"API Recognition service failed: {e}")
            return response

    def training_service(self, request, response):
        try:
            cmd_type = request.cmd_type.data
            args = json.loads(request.args.data)
            target_tid = args.pop("tid", None)

            if cmd_type in self.training_dispatcher:
                result, message = self.training_dispatcher[cmd_type](**args)
                
                if result >= 0:
                    with self.state_lock:
                        tids = [target_tid] if target_tid is not None else list(self.pending_naming)
                        for t in tids:
                            self.pending_naming.discard(t)
                            self.pending_confirmation.discard(t)
                            if t in self.recognition_cache:
                                new_name = args.get("class_name", args.get("name", args.get("label")))
                                if new_name:
                                    self.recognition_cache[t]['faceprint']['name'] = new_name
                                if cmd_type == "add_class" and isinstance(message, dict) and "id" in message:
                                    self.recognition_cache[t]['faceprint']['id'] = str(message["id"])
                                self.recognition_cache[t]['distance'] = 1.0
                            self.retry_count[t] = 0
            elif cmd_type == "cancel":
                with self.state_lock:
                    tids = [target_tid] if target_tid is not None else list(self.pending_naming | self.pending_confirmation)
                    for t in tids:
                        self.pending_naming.discard(t)
                        self.pending_confirmation.discard(t)
                        self.retry_count[t] = 0
                result, message = 0, "Cancelled"
            else:
                result, message = -1, f"Unknown command: {cmd_type}"
        except Exception as e:
            result, message = -1, f"Error: {e}"

        response.result = result
        response.message.data = str(message["id"] if cmd_type == "add_class" and result >= 0 else message)
        return response

    def get_people_service(self, request, response):
        args = json.loads(request.args) if request.args else {}
        if args.get("id"):
            result = self.classifier.db.get_by_id(args["id"])
        else:
            result = self.classifier.db.get_all(args.get("name", ""))
        response.text = json.dumps(result)
        return response

    def clear_no_name_service(self, request, response):
        self.classifier.clear_no_name()
        return response

    def set_learn_without_name_service(self, request, response):
        return response

    def _entry_to_recognition(self, entry: dict) -> FaceRecognition:
        faceprint = entry['faceprint']
        recog = FaceRecognition()
        recog.classified_id = faceprint.get('id', '')
        recog.classified_name = faceprint.get('name', 'Unknown')
        recog.distance = float(entry.get('distance', 0.0))
        recog.features = [float(f) for f in entry.get('features', [])]
        if entry.get('pos'):
            recog.pos = entry['pos'] 
        recog.face_updated = bool(entry.get('face_updated', False))

        if entry['face_aligned'] is not None and hasattr(entry['face_aligned'], 'shape'):
            recog.face_aligned = self.bridge.cv2_to_imgmsg(entry['face_aligned'], encoding="bgr8")
        else:
            recog.face_aligned = Image()
            recog.face_aligned.encoding = "bgr8" 
        return recog

def main(args=None):
    rclpy.init(args=args)
    node = BodyFaceFusionNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.inference_pool.shutdown(wait=False)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()