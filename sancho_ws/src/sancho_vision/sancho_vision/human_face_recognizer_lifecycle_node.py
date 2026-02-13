import json
import rclpy
import threading
import time

from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile

from std_msgs.msg import String
from std_srvs.srv import SetBool, Empty
from sensor_msgs.msg import Image
from sancho_msgs.msg import FaceDetection, FaceDetectionArray, FaceRecognition, FaceRecognitionArray
from geometry_msgs.msg import Point
from hri_msgs.msg import FaceprintEvent
from hri_msgs.srv import Recognition, Training, GetString

from .hri_bridge import HRIBridge
from .aligners.aligner_dlib import align_face
from .classifiers.complex_classifier import ComplexClassifier
from .encoders import load_encoder
from .api.gui_utils import mark_face

class HumanFaceRecognizerLifecycleNode(LifecycleNode):

    def __init__(self):
        super().__init__("human_face_recognizer")

        self.declare_parameters(namespace='', parameters=[
            ("detections_topic", "/face_detections"),
            ("recognitions_topic", "/face_recognitions"),
            ("encoder_name", "facenet"),
            ("db_mode", "save"),
            ("learn_without_name", True),
            ("processing_rate", 10.0),
            ("recognition_cache_ttl", 10.0),
            ("recognition_cache_max_size", 20),
        ])

        self.bridge = HRIBridge()

        self.classifier = None
        self.encoder = None

        self.sub_dets = None
        self.pub_faceprint_event = None
        self.pub_recog = None
        self.pub_img_recog = None

        self.recognition_srv = None
        self.training_srv = None
        self.clear_no_name_srv = None
        self.get_faceprint_srv = None
        self.set_learn_without_name_srv = None

        # recognition cache: tracker_id -> entry dict
        # entry: {
        #   'face_aligned', 'features', 'faceprint', 'distance', 'pos',
        #   'face_updated', 'confidence', 'last_seen'
        # }
        self.recognition_cache = {}

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo de reconocimiento...")

        self.detections_topic = self.get_parameter("detections_topic").value
        self.recognitions_topic = self.get_parameter("recognitions_topic").value
        self.encoder_name = self.get_parameter("encoder_name").value
        self.db_mode = self.get_parameter("db_mode").value
        self.learn_without_name = self.get_parameter("learn_without_name").value
        self.processing_rate = self.get_parameter("processing_rate").value
        self.cache_ttl = float(self.get_parameter("recognition_cache_ttl").value)
        self.cache_max_size = int(self.get_parameter("recognition_cache_max_size").value)

        try:
            self.encoder = load_encoder(self.encoder_name)
        except Exception as e:
            self.get_logger().error(f"Error cargando reconocedor '{self.encoder_name}': {e}")
            return TransitionCallbackReturn.FAILURE
    
        self.classifier = ComplexClassifier(self.db_mode)

        qos1 = QoSProfile(depth=1)
        qos10 = QoSProfile(depth=10)
        self.pub_faceprint_event = self.create_publisher(FaceprintEvent, "recognition/event", qos10)
        self.pub_recog = self.create_lifecycle_publisher(FaceRecognitionArray, self.recognitions_topic, qos1)
        self.pub_img_recog = self.create_lifecycle_publisher(Image, 'camera/color/recognition', qos1)

        self.recognition_srv = self.create_service(Recognition, "recognition", self.recognition_service)
        self.training_srv = self.create_service(Training, "recognition/training", self.training_service)
        self.get_faceprint_srv = self.create_service(GetString, "recognition/get_faceprint", self.get_people_service)
        self.clear_no_name_srv = self.create_service(Empty, "recognition/clear_no_name", self.clear_no_name_service)
        self.set_learn_without_name_srv = self.create_service(SetBool, "recognition/set_learn_without_name", self.set_learn_without_name_service)

        self.training_dispatcher = {
            "refine_class": self.classifier.refine_class,
            "add_features": self.classifier.add_features,
            "add_class": self.classifier.add_class,
            "rename_class": self.classifier.rename_class,
            "delete_class": self.classifier.delete_class,
            "delete_all": self.classifier.delete_all
        }

        self.faceprint_event_map = {
            "add_class": FaceprintEvent.CREATE,
            "delete_class": FaceprintEvent.DELETE,
            "rename_class": FaceprintEvent.UPDATE,
            "add_features": FaceprintEvent.UPDATE,
            "delete_all": FaceprintEvent.DELETE_ALL
        }

        return super().on_configure(state)

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo de reconocimiento...")

        qos = QoSProfile(depth=1)
        self.sub_dets = self.create_subscription(FaceDetectionArray, self.detections_topic, self.detections_callback, qos)

        self._lock = threading.Lock()
        self.lastest_detections = None
        self.save_db_timer = self.create_timer(10.0, lambda: self.classifier.db.save())
        self.cache_prune_timer = self.create_timer(5.0, self.prune_cache)
        self.spin_timer = self.create_timer(1.0 / self.processing_rate, self.spin)

        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo de reconocimiento...")

        self.lastest_detections = None

        if self.spin_timer:
            self.spin_timer.cancel()
            self.spin_timer = None

        if self.cache_prune_timer:
            self.cache_prune_timer.cancel()
            self.cache_prune_timer = None

        if self.save_db_timer:
            self.save_db_timer.cancel()
            self.save_db_timer = None

        if self.sub_dets:
            self.destroy_subscription(self.sub_dets)
            self.sub_dets = None

        if self._lock:
            self._lock = None

        return super().on_deactivate(state)

    def detections_callback(self, msg: FaceDetectionArray):
        with self._lock:
            self.lastest_detections = msg

    def prune_cache(self):
        '''Llamada periódicamente para eliminar entradas de la caché'''
        self.get_logger().info("Ejecutando prune_cache()...")
        now = time.monotonic()

        lock = getattr(self, "_lock", None)
        if lock:
            lock.acquire()
        try:
            # Eliminar entradas que superan el TTL
            expired = [tid for tid, e in self.recognition_cache.items() if (now - e.get("last_seen", 0)) > self.cache_ttl]
            for tid in expired:
                del self.recognition_cache[tid]
                self.get_logger().info(f"Eliminada entrada expirada con id {tid} de la caché")

            # Eliminar entradas que llevan más tiempo sin verse para ajustarse al tamaño máximo
            if len(self.recognition_cache) > self.cache_max_size:
                # Ordenar ids por 'last_seen' (más viejos primero)
                sorted_ids = sorted(self.recognition_cache.items(), key=lambda kv: kv[1].get("last_seen", 0))
                # Eliminar más antiguas hasta que el tamaño esté bien
                for tid, _ in sorted_ids[:len(self.recognition_cache) - self.cache_max_size]:
                    if tid in self.recognition_cache:
                        del self.recognition_cache[tid]
                        self.get_logger().info(f"Eliminada entrada con id {tid} de la caché por política LRU")
        finally:
            if lock:
                lock.release()
    
    def spin(self):
        with self._lock:
            msg = self.lastest_detections
            self.lastest_detections = None

        if msg is None:
            return
        
        recognitions, marked_img_msg = self.recognize(msg.image, msg.detections, self.learn_without_name)

        msg_out = FaceRecognitionArray()
        msg_out.header = msg.header
        msg_out.image = marked_img_msg if marked_img_msg is not None else msg.image
        msg_out.detections = msg.detections

        for face_aligned, features, faceprint, distance, pos, face_updated in recognitions:
            recog = FaceRecognition(
                face_aligned=self.bridge.cv2_to_imgmsg(face_aligned, "bgr8"),
                features=features,
                classified_id=faceprint["id"],
                classified_name=faceprint["name"],
                distance=distance,
                pos=pos,
                face_updated=face_updated
            )

            msg_out.recognitions.append(recog)

        self.pub_recog.publish(msg_out)

    def recognition_service(self, request, response):
        [rx, ry, rw, rh] = [request.position.x, request.position.y, request.position.w, request.position.h]
        face_detection = FaceDetection(corner=Point(x=float(rx), y=float(ry)), width=float(rw), height=float(rh), confidence=request.score)

        recognitions, _ = self.recognize(request.frame, [face_detection], publish_marked_img=False)
        if not recognitions:
            self.get_logger().warn("Recognition service received no results for provided detection.")
            return response

        face_aligned, features, faceprint, distance, pos, face_updated = recognitions[0]

        response.face_aligned = self.bridge.cv2_to_imgmsg(face_aligned, "bgr8")
        response.features = [float(f) for f in features]
        response.classified_id = faceprint["id"]
        response.classified_name = faceprint["name"]
        response.distance = distance
        response.pos = pos
        response.face_updated = face_updated

        return response

    def recognize(self, frame, detections, learn_without_name=False, publish_marked_img=True):
        if isinstance(frame, Image): # Normaliza el frame si viene como sensor_msgs/Image
            frame = self.bridge.imgmsg_to_cv2(frame, "bgr8")

        marked_image = frame.copy()
        recognitions = []
        now = time.monotonic()

        for det in detections:
            position = [det.corner.x, det.corner.y, det.width, det.height]
            confidence = det.confidence
            tracker_id = int(det.tid) if hasattr(det, "tid") else 0

            # Utilizamos el id del tracker para consultar la cache
            if tracker_id and tracker_id in self.recognition_cache:
                entry = self.recognition_cache[tracker_id] 
                entry['last_seen'] = now

                face_aligned = entry['face_aligned']
                features = entry['features']
                faceprint = entry['faceprint']
                distance = entry['distance']
                pos = entry['pos']
                face_updated = entry['face_updated']

                display_name = "Unknown" if not faceprint["id"] else (faceprint["name"] if faceprint["name"] else f"User-{faceprint['id']}")
                self.get_logger().info(f"[cached] {display_name} -> Distance: {distance:.4f} | Confidence: {confidence:.4f}")

                mark_face(marked_image, [int(i) for i in position], distance, 0.80, 0.90, display_name, score=confidence, showDistance=True, showScore=True)

                recognitions.append((face_aligned, features, faceprint, distance, pos, face_updated))
                continue

            # No hay entrada en la cache: preprocesar cara, calcular embedding y clasificarlo
            face_aligned = align_face(frame, position)
            features = self.encoder.encode_face(face_aligned)
            faceprint, distance, pos = self.classifier.classify_face(features)

            face_updated = False # Ver si quitar esto de face_updated que no se para que es necesario
            if confidence >= 1.0 and distance >= 0.90: # Poner los thresholds en un archivo bien definido o algo asi
                self.classifier.refine_class(faceprint["id"], features, pos)
                face_updated = self.classifier.save_face(faceprint["id"], face_aligned, confidence)
                if face_updated:
                    self.send_faceprint_event(FaceprintEvent.UPDATE, faceprint["id"], FaceprintEvent.ORIGIN_ROS)

            if distance < 0.75: # Si es menor que el limite inferior
                if learn_without_name and confidence >= 1.0: # Si aprender sin nombre y buena calidad, aprendemos
                    face = self.bridge.cv2_to_base64(face_aligned)
                    distance = 1.0

                    _, faceprint = self.classifier.add_class("", features, face, confidence)
                
                else: # Si no lo marcamos como desconocido
                    faceprint, distance, pos = {"id": "", "name": ""}, 0.0, 0

            display_name = "Unknown" if not faceprint["id"] else (faceprint["name"] if faceprint["name"] else f"User-{faceprint['id']}")
            self.get_logger().info(f"{display_name} -> Distance: {distance:.4f} | Confidence: {confidence:.4f}")
            
            mark_face(marked_image, [int(i) for i in position], distance, 0.80, 0.90, display_name, score=confidence, showDistance=True, showScore=True)

            # Actualizar la cache
            if tracker_id and faceprint["id"]:
                self.recognition_cache[tracker_id] = {
                    'face_aligned': face_aligned,
                    'features': features,
                    'faceprint': faceprint,
                    'distance': distance,
                    'pos': pos,
                    'face_updated': face_updated,
                    'confidence': confidence,
                    'last_seen': now,
                }

            recognitions.append((face_aligned, features, faceprint, distance, pos, face_updated))

        marked_img_msg = None # Si eso mover todo esto a assistant helper que ahi se determina al interlocutor
        if publish_marked_img:
            marked_img_msg = self.bridge.cv2_to_imgmsg(marked_image, "bgr8")
            self.pub_img_recog.publish(marked_img_msg)

        return recognitions, marked_img_msg

    def training_service(self, request, response):
        try:
            cmd_type = request.cmd_type.data
            args = json.loads(request.args.data)
            origin = request.origin
        except json.JSONDecodeError as e:
            response.result = -1
            response.message = String(data=f"Invalid JSON: {e}")
            return response

        self.get_logger().info(f"Training command received: {cmd_type}")

        try:
            function = self.training_dispatcher[cmd_type]
            result, message = function(**args)
        except Exception as e:
            result, message = -1, f"Error ejecutando {cmd_type}: {e}"

        if result >= 0 and "class_name" in args:
            event = self.faceprint_event_map.get(cmd_type)
            if event is not None:
                id = message["id"] if cmd_type == "add_class" else args["class_id"]
                self.send_faceprint_event(event, id, origin)

        response.result = result
        response.message = String(data=str(message["id"] if cmd_type == "add_class" and result >= 0 else message))
        return response

    def get_people_service(self, request, response):
        args = json.loads(request.args) if request.args else {}
        id = args.get("id", "").strip()
        name = args.get("name", "").strip()
        fields = args.get("fields", [])

        def filter_fields(obj):
            return {k: obj[k] for k in fields if k in obj} if fields else obj

        if id:
            result = self.classifier.db.get_by_id(id)
            result = filter_fields(result) if result else {}
        else:
            result = self.classifier.db.get_all(name)
            result = [filter_fields(fp) for fp in result]

        response.text = json.dumps(result)
        return response

    def clear_no_name_service(self, request, response):
        _, removed_ids = self.classifier.clear_no_name()

        for id in removed_ids:
            self.send_faceprint_event(FaceprintEvent.DELETE, id, FaceprintEvent.ORIGIN_ROS)

        return response

    def set_learn_without_name_service(self, request, response):
        self.learn_without_name = request.data

        return response

    def send_faceprint_event(self, event, id, origin):
        faceprint_event = FaceprintEvent()
        faceprint_event.event = event
        faceprint_event.id = id
        faceprint_event.origin = origin
        self.pub_faceprint_event.publish(faceprint_event)

def main(args=None):
    rclpy.init(args=args)

    lifecycle_node = HumanFaceRecognizerLifecycleNode()

    rclpy.spin(lifecycle_node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
