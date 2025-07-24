import json
import time
from enum import Enum

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from hri_msgs.msg import FaceprintEvent
from hri_msgs.srv import Recognition, Training, GetString

from .hri_bridge import HRIBridge
from .aligners.aligner_dlib import align_face
from .classifiers.complex_classifier import ComplexClassifier

from .encoders import ( BaseEncoder,
    FacenetEncoder, ArcFaceEncoder, DinoV2Encoder,
    OpenFaceEncoder, SFaceEncoder, VGGFaceEncoder
)

class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class DBMode(SmartStrEnum):
    SAVE = "save",
    NO_SAVE = "no_save"

class EncoderType(SmartStrEnum):
    FACENET = "facenet"
    ARCFACE = "arcface"
    DINOV2 = "dinov2"
    OPENFACE = "openface"
    SFACE = "sface"
    VGGFACE = "vggface"


ENCODER_CLASS_MAP = {
    EncoderType.FACENET: FacenetEncoder,
    EncoderType.ARCFACE: ArcFaceEncoder,
    EncoderType.DINOV2: DinoV2Encoder,
    EncoderType.OPENFACE: OpenFaceEncoder,
    EncoderType.SFACE: SFaceEncoder,
    EncoderType.VGGFACE: VGGFaceEncoder,
}


class HumanFaceRecognizer(Node):

    def __init__(self):
        super().__init__("human_face_recognizer")

        self.show_metrics = self.declare_parameter("show_metrics", False).value
        encoder_name = self.declare_parameter("encoder_name", EncoderType.FACENET).value.lower()
        db_mode = self.declare_parameter("db_mode", DBMode.SAVE).value.lower()

        try:
            encoder_type = EncoderType(encoder_name)
        except ValueError:
            self.get_logger().warn(f"Encoder '{encoder_name}' no reconocido. Usando 'facenet' por defecto.")
            encoder_type = EncoderType.FACENET

        self.encoder: BaseEncoder = ENCODER_CLASS_MAP[encoder_type]()
        self.get_logger().info(f"Encoder seleccionado: {encoder_type} ({self.encoder.__class__.__name__})")

        self.recognition_service = self.create_service(Recognition, "recognition", self.recognition)
        self.training_service = self.create_service(Training, "recognition/training", self.training)
        self.get_faceprint_service = self.create_service(GetString, "recognition/get_faceprint", self.get_people)

        self.faceprint_event_pub = self.create_publisher(FaceprintEvent, "recognition/event", 10)

        self.classifier = ComplexClassifier(db_mode)
        self.save_db_timer = self.create_timer(10.0, self.save_data)

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

        self.br = HRIBridge()

    def recognition(self, request, response):
        frame = self.br.imgmsg_to_cv2(request.frame, "bgr8")
        position = [
            request.position.x,
            request.position.y,
            request.position.w,
            request.position.h,
        ]
        score = request.score

        face_aligned = align_face(frame, position)

        start_recognition = time.time()
        features = self.encoder.encode_face(face_aligned)
        recognition_time = time.time() - start_recognition
        
        faceprint, distance, pos = self.classifier.classify_face(features)

        classified_id = faceprint["id"] if faceprint else None
        classified_name = faceprint["name"] if faceprint else None

        UPPER_BOUND = 0.9
        face_updated = False
        if faceprint and score >= 1 and distance >= UPPER_BOUND:
            face_updated = self.classifier.save_face(classified_id, face_aligned, score)
            if face_updated:
                self.send_faceprint_event(FaceprintEvent.UPDATE, classified_id, FaceprintEvent.ORIGIN_ROS)

        face_aligned_msg, features_msg, classified_name_msg, distance_msg, pos_msg = (
            self.br.recognizer_to_msg(face_aligned, features, classified_name, distance, pos)
        )

        response.face_aligned = face_aligned_msg
        response.features = features_msg
        response.classified_id = str(classified_id)
        response.classified_name = classified_name_msg
        response.distance = distance_msg
        response.pos = pos_msg
        response.face_updated = face_updated
        
        response.recognition_time = recognition_time
        if self.show_metrics:
            self.get_logger().info("Recognition time: " + str(recognition_time))

        return response

    def training(self, request, response):
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
            result, message = -1, f"Error executing {cmd_type}: {e}"

        if result >= 0 and "class_name" in args:
            event = self.faceprint_event_map.get(cmd_type)
            if event is not None:
                id = message if cmd_type == "add_class" else args["class_id"]
                self.send_faceprint_event(event, id, origin)

        response.result = result
        response.message = String(data=str(message))
        return response

    def send_faceprint_event(self, event, id, origin):
        faceprint_event = FaceprintEvent()
        faceprint_event.event = event
        faceprint_event.id = id
        faceprint_event.origin = origin
        self.faceprint_event_pub.publish(faceprint_event)

    def get_people(self, request, response):
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

    def save_data(self):
        self.classifier.db.save()


def main(args=None):
    rclpy.init(args=args)
    node = HumanFaceRecognizer()
    rclpy.spin(node)
    rclpy.shutdown()
