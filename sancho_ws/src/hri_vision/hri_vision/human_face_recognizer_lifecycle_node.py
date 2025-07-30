import json
import time

import cv2
import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile

from std_msgs.msg import String
from sensor_msgs.msg import Image
from sancho_msgs.msg import FaceDetectionArray, FaceRecognition, FaceRecognitionArray
from hri_msgs.msg import FaceprintEvent
from hri_msgs.srv import Recognition, Training, GetString

from .hri_bridge import HRIBridge
from .aligners.aligner_dlib import align_face
from .classifiers.complex_classifier import ComplexClassifier
from .encoders import load_encoder


class HumanFaceRecognizerLifecycle(LifecycleNode):

    def __init__(self):
        super().__init__("human_face_encoder")

        self.declare_parameters(namespace='', parameters=[
            ("detections_topic", "/face_detections"),
            ("recognitions_topic", "/face_recognitions"),
            ("encoder_name", "facenet"),
            ("db_mode", "save"),
            ("show_metrics", False)
        ])

        self.bridge = HRIBridge()
        self.classifier = None
        self.encoder = None
        self.sub_dets = None
        self.pub_recog = None

        self.recognition_srv = None
        self.training_srv = None
        self.get_faceprint_srv = None
        self.faceprint_event_pub = None

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo de reconocimiento...")

        self.detections_topic = self.get_parameter("detections_topic").value
        self.recognitions_topic = self.get_parameter("recognitions_topic").value
        self.encoder_name = self.get_parameter("encoder_name").value
        self.db_mode = self.get_parameter("db_mode").value
        self.show_metrics = self.get_parameter("show_metrics").value

        try:
            self.encoder = load_encoder(self.encoder_name)
        except Exception as e:
            self.get_logger().error(f"Error cargando reconocedor '{self.encoder_name}': {e}")
            return TransitionCallbackReturn.FAILURE

        self.classifier = ComplexClassifier(self.db_mode)

        qos = QoSProfile(depth=10)
        self.faceprint_event_pub = self.create_publisher(FaceprintEvent, "recognition/event", qos)
        self.pub_recog = self.create_lifecycle_publisher(FaceRecognitionArray, self.recognitions_topic, qos)

        self.recognition_srv = self.create_service(Recognition, "recognition", self.recognition_service)
        self.training_srv = self.create_service(Training, "recognition/training", self.training_service)
        self.get_faceprint_srv = self.create_service(GetString, "recognition/get_faceprint", self.get_people_service)

        self.training_dispatcher = {
            "refine_class": self.classifier.refine_class,
            "add_features": self.classifier.add_features,
            "add_class": self.classifier.add_class,
            "rename_class": self.classifier.rename_class,
            "delete_class": self.classifier.delete_class
        }

        self.faceprint_event_map = {
            "add_class": FaceprintEvent.CREATE,
            "delete_class": FaceprintEvent.DELETE,
            "rename_class": FaceprintEvent.UPDATE,
            "add_features": FaceprintEvent.UPDATE,
        }

        self.save_db_timer = self.create_timer(10.0, self.save_data)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo de reconocimiento...")

        qos = QoSProfile(depth=10)
        self.sub_dets = self.create_subscription(FaceDetectionArray, self.detections_topic, self.detection_callback, qos)

        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo de reconocimiento...")

        if self.sub_dets:
            self.destroy_subscription(self.sub_dets)
            self.sub_dets = None

        return TransitionCallbackReturn.SUCCESS

    def detection_callback(self, msg: FaceDetectionArray):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg.image, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Error convirtiendo imagen: {e}")
            return

        msg_out = FaceRecognitionArray()
        msg_out.header = msg.header
        msg_out.image = msg.image
        msg_out.detections = msg.detections

        for det in msg.detections:
            pos = [det.x, det.y, det.width, det.height]
            face_aligned = align_face(frame, pos)
            features = self.encoder.encode_face(face_aligned)
            faceprint, distance, rank = self.classifier.classify_face(features)

            classified_id = faceprint["id"] if faceprint else ""
            classified_name = faceprint["name"] if faceprint else ""
            updated = False
            if faceprint and det.confidence >= 1 and distance >= 0.9:
                updated = self.classifier.save_face(classified_id, face_aligned, det.confidence)
                if updated:
                    self.send_faceprint_event(FaceprintEvent.UPDATE, classified_id, FaceprintEvent.ORIGIN_ROS)

            recog = FaceRecognition()
            recog.face_aligned = self.bridge.cv2_to_imgmsg(face_aligned, "bgr8")
            recog.features = features
            recog.classified_id = classified_id
            recog.classified_name = classified_name
            recog.distance = distance
            recog.pos = rank
            recog.face_updated = updated

            msg_out.recognitions.append(recog)

        self.pub_recog.publish(msg_out)

    def recognition_service(self, request, response):
        try:
            frame = self.bridge.imgmsg_to_cv2(request.frame, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Error al convertir imagen del servicio: {e}")
            response.result = -1
            response.message = String(data="Error al procesar imagen")
            return response

        position = [
            request.position.x,
            request.position.y,
            request.position.w,
            request.position.h,
        ]
        score = request.score

        try:
            face_aligned = align_face(frame, position)
        except Exception as e:
            self.get_logger().warn(f"Error al alinear rostro: {e}")
            response.result = -1
            response.message = String(data="No se pudo alinear el rostro")
            return response

        start_time = time.time()
        features = self.encoder.encode_face(face_aligned)
        recog_time = time.time() - start_time

        faceprint, distance, pos = self.classifier.classify_face(features)

        classified_id = faceprint["id"] if faceprint else ""
        classified_name = faceprint["name"] if faceprint else ""
        updated = False
        if faceprint and score >= 1 and distance >= 0.9:
            updated = self.classifier.save_face(classified_id, face_aligned, score)
            if updated:
                self.send_faceprint_event(FaceprintEvent.UPDATE, classified_id, FaceprintEvent.ORIGIN_ROS)

        aligned_msg = self.bridge.cv2_to_imgmsg(face_aligned, "bgr8")

        response.face_aligned = aligned_msg
        response.features = features
        response.classified_id = classified_id
        response.classified_name = classified_name
        response.distance = distance
        response.pos = pos
        response.face_updated = updated
        response.recognition_time = recog_time
        response.result = 0
        response.message = String(data="Reconocimiento exitoso")

        if self.show_metrics:
            self.get_logger().info(f"[Servicio] Reconocimiento de '{classified_name}' en {recog_time:.3f}s")

        return response

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
                id = message if cmd_type == "add_class" else args["class_id"]
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

    def send_faceprint_event(self, event, id, origin):
        faceprint_event = FaceprintEvent()
        faceprint_event.event = event
        faceprint_event.id = id
        faceprint_event.origin = origin
        self.faceprint_event_pub.publish(faceprint_event)

    def save_data(self):
        self.classifier.db.save()


def main(args=None):
    rclpy.init(args=args)
    node = HumanFaceRecognizerLifecycle()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
