import json

import rclpy
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


class HumanFaceRecognizerLifecycleNode(LifecycleNode):

    def __init__(self):
        super().__init__("human_face_recognizer")

        self.declare_parameters(namespace='', parameters=[
            ("detections_topic", "/face_detections"),
            ("recognitions_topic", "/face_recognitions"),
            ("encoder_name", "facenet"),
            ("db_mode", "save"),
            ("learn_without_name", True),
            ("processing_rate", 10.0)
        ])

        self.bridge = HRIBridge()

        self.classifier = None
        self.encoder = None

        self.sub_dets = None
        self.pub_recog = None
        self.pub_faceprint_event = None

        self.recognition_srv = None
        self.training_srv = None
        self.clear_no_name_srv = None
        self.get_faceprint_srv = None
        self.set_learn_without_name_srv = None

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo de reconocimiento...")

        self.detections_topic = self.get_parameter("detections_topic").value
        self.recognitions_topic = self.get_parameter("recognitions_topic").value
        self.encoder_name = self.get_parameter("encoder_name").value
        self.db_mode = self.get_parameter("db_mode").value
        self.learn_without_name = self.get_parameter("learn_without_name").value
        self.processing_rate = self.get_parameter("processing_rate").value

        try:
            self.encoder = load_encoder(self.encoder_name)
        except Exception as e:
            self.get_logger().error(f"Error cargando reconocedor '{self.encoder_name}': {e}")
            return TransitionCallbackReturn.FAILURE
    
        self.classifier = ComplexClassifier(self.db_mode)

        qos = QoSProfile(depth=10)
        self.pub_faceprint_event = self.create_publisher(FaceprintEvent, "recognition/event", qos)
        self.pub_recog = self.create_lifecycle_publisher(FaceRecognitionArray, self.recognitions_topic, qos)

        self.recognition_srv = self.create_service(Recognition, "recognition", self.recognition_service)
        self.training_srv = self.create_service(Training, "recognition/training", self.training_service)
        self.get_faceprint_srv = self.create_service(GetString, "recognition/get_faceprint", self.get_people_service)
        self.clear_no_name_srv = self.create_service(Empty, "recognition/clear_no_name", self.set_learn_without_name_service)
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

        qos = QoSProfile(depth=10)
        self.sub_dets = self.create_subscription(FaceDetectionArray, self.detections_topic, self.detections_callback, qos)

        self.last_detections = None
        self.save_db_timer = self.create_timer(10.0, lambda: self.classifier.db.save())
        self.spin_timer = self.create_timer(1.0 / self.processing_rate, self.spin)

        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo de reconocimiento...")

        if self.spin_timer:
            self.spin_timer.cancel()
            self.spin_timer = None

        if self.save_db_timer:
            self.save_db_timer.cancel()
            self.save_db_timer = None

        if self.sub_dets:
            self.destroy_subscription(self.sub_dets)
            self.sub_dets = None

        return super().on_deactivate(state)

    def detections_callback(self, msg: FaceDetectionArray):
        self.last_detections = msg
    
    def spin(self):
        if self.last_detections is None:
            return
        
        msg = self.last_detections
        msg_out = FaceRecognitionArray()
        msg_out.header = msg.header
        msg_out.image = msg.image
        msg_out.detections = msg.detections

        for recog in self.recognize(msg.image, msg.detections):
            face_aligned, features, faceprint, distance, pos, face_updated = recog

            recog = FaceRecognition(
                face_aligned = self.bridge.cv2_to_imgmsg(face_aligned, "bgr8"),
                features = features,
                classified_id = faceprint["id"],
                classified_name = faceprint["name"],
                distance = distance,
                pos = pos,
                face_updated = face_updated
            )
            
            msg_out.recognitions.append(recog)

        self.pub_recog.publish(msg_out)

    def recognition_service(self, request, response):
        [rx, ry, rw, rh] = [request.position.x, request.position.y, request.position.w, request.position.h]
        face_detection = FaceDetection(corner=Point(x=rx, y=ry), width=rw, height=rh, confidence=request.score)

        face_aligned, features, faceprint, distance, pos, face_updated = self.recognize(request.frame, [face_detection])[0]

        response.face_aligned = self.bridge.cv2_to_imgmsg(face_aligned, "bgr8")
        response.features = features
        response.classified_id = faceprint["id"]
        response.classified_name = faceprint["name"]
        response.distance = distance
        response.pos = pos
        response.face_updated = face_updated
        response.result = 0
        response.message = String(data="Reconocimiento exitoso")

        return response

    def recognize(self, frame, detections):
        if isinstance(frame, Image): # Normaliza el frame si viene como sensor_msgs/Image
            frame = self.bridge.imgmsg_to_cv2(frame, "bgr8")

        for det in detections:
            pos = [det.corner.x, det.corner.y, det.width, det.height]
            confidence = det.confidence

            face_aligned = align_face(frame, pos)
            features = self.encoder.encode_face(face_aligned)
            faceprint, distance, pos = self.classifier.classify_face(features)

            face_updated = False # Ver si quitar esto de face_updated que no se para que es necesario
            if confidence >= 1.0 and distance >= 0.90: # Poner los thresholds en un archivo bien definido o algo asi
                self.classifier.refine_class(faceprint["id"], features, pos)
                face_updated = self.classifier.save_face(faceprint["id"], face_aligned, confidence)
                if face_updated:
                    self.send_faceprint_event(FaceprintEvent.UPDATE, faceprint["id"], FaceprintEvent.ORIGIN_ROS)

            if self.learn_without_name and confidence >= 1.0 and distance < 0.75: # Ir ajustando el valor de distance 
                face = self.bridge.cv2_to_base64(face_aligned)
                distance = 1.0

                _, faceprint = self.classifier.add_class("", features, face, confidence)

            self.get_logger().info(f"{faceprint['name'] or faceprint['id'] or 'Not classified'} -> Distance: {distance:.4f} | Confidence: {confidence:.4f}")

            yield face_aligned, features, faceprint, distance, pos, face_updated

    def training_service(self, request, response):
        try:
            cmd_type = request.cmd_type.data
            args = json.loads(request.args.data)
            origin = request.origin
        except json.JSONDecodeError as e:
            response.result = -1
            response.message = String(data=f"Invalid JSON: {e}")
            return response

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
        response.message = String(data=str(message))
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
        removed_ids = self.classifier.clear_no_name()
        
        response.success = True
        response.message = String(data=f"Removed {len(removed_ids)} faceprints without name")

        for id in removed_ids:
            self.send_faceprint_event(FaceprintEvent.DELETE, id, FaceprintEvent.ORIGIN_ROS)

        return response

    def set_learn_without_name_service(self, request, response):
        self.learn_without_name = request.data

        response.success = True
        response.message = String(data=f"Needs name set to {request.data}")

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
