import json
from queue import Queue

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile

from std_msgs.msg import String, Empty
from hri_msgs.srv import Training, TriggerUserInteraction
from hri_msgs.msg import Log, FaceNameResponse, FaceQuestionResponse
from sancho_msgs.msg import FaceRecognitionArray

from sancho_web_assistant.database.system_database import CONSTANTS
from .database.people_manager import PeopleManager
from .api.gui_utils import mark_face
from .hri_bridge import HRIBridge


class HumanFaceManagerLifecycleNode(LifecycleNode):
    def __init__(self):
        super().__init__("human_face_manager")

        self.human_face_manager = HumanFaceManager(self)

        self.declare_parameters(namespace="", parameters=[
            ("face_recognitions_topic", "/face_recognitions"),
            ("gui_face_name_response_topic", "gui/face_name_response"),
            ("gui_face_question_response_topic", "gui/face_question_response"),
            ("gui_face_timeout_response_topic", "gui/face_timeout_response"),
            ("logs_topic", "logs/add"),
            ("camera_recognition_topic", "camera/color/recognition"),
            ("people_topic", "logic/info/actual_people"),
            ("input_tts_topic", "input_tts"),
            ("processing_rate", 10.0),
            ("service_wait_attempts", 10),
            ("service_wait_timeout_sec", 0.5),
        ])

        self.bridge = HRIBridge()

        self.face_recognitions_queue = Queue()
        self.face_name_queue = Queue()
        self.face_question_queue = Queue()

        self.sub_face_name = None
        self.sub_face_question = None
        self.sub_face_timeout = None
        self.sub_recognitions = None
        self.pub_log = None
        self.pub_recognition = None
        self.pub_people = None
        self.pub_input_tts = None

        self.training_client = None
        self.gui_client = None

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo manejador de rostros...")

        self.face_recognitions_topic = self.get_parameter("face_recognitions_topic").value
        self.gui_face_name_response_topic = self.get_parameter("gui_face_name_response_topic").value
        self.gui_face_question_response_topic = self.get_parameter("gui_face_question_response_topic").value
        self.gui_face_timeout_response_topic = self.get_parameter("gui_face_timeout_response_topic").value
        self.logs_topic = self.get_parameter("logs_topic").value
        self.camera_recognition_topic = self.get_parameter("camera_recognition_topic").value
        self.people_topic = self.get_parameter("people_topic").value
        self.input_tts_topic = self.get_parameter("input_tts_topic").value
        self.processing_rate = float(self.get_parameter("processing_rate").value)
        self.service_wait_attempts = int(self.get_parameter("service_wait_attempts").value)
        self.service_wait_timeout_sec = float(self.get_parameter("service_wait_timeout_sec").value)

        qos10 = QoSProfile(depth=10)
        qos1 = QoSProfile(depth=1)
        self.pub_log = self.create_lifecycle_publisher(Log, self.logs_topic, qos10)
        self.pub_recognition = self.create_lifecycle_publisher(String, self.camera_recognition_topic, qos1)
        self.pub_people = self.create_lifecycle_publisher(String, self.people_topic, qos1)
        self.pub_input_tts = self.create_lifecycle_publisher(String, self.input_tts_topic, qos10)

        self.training_client = self.create_client(Training, "recognition/training")
        while not self.training_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Training service not available, waiting again...')

        self.gui_client = self.create_client(TriggerUserInteraction, "gui/request")
        while not self.gui_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('GUI service not available, waiting again...')

        return super().on_configure(state)

    def on_activate(self, state) -> TransitionCallbackReturn:
        qos10 = QoSProfile(depth=10)
        qos1 = QoSProfile(depth=1)
        self.sub_face_name = self.create_subscription(FaceNameResponse, self.gui_face_name_response_topic, self.face_name_response_callback, qos10)
        self.sub_face_question = self.create_subscription(FaceQuestionResponse, self.gui_face_question_response_topic, self.face_question_response_callback, qos10)
        self.sub_face_timeout = self.create_subscription(Empty, self.gui_face_timeout_response_topic, self.face_timeout_response_callback, qos10)
        self.sub_recognitions = self.create_subscription(FaceRecognitionArray, self.face_recognitions_topic, self.recognitions_callback, qos1)

        self.face_timeout_response = False
        self.spin_timer = self.create_timer(1.0 / self.processing_rate, self.human_face_manager.spin)

        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo manejador de rostros...")

        if self.spin_timer:
            self.spin_timer.cancel()
            self.spin_timer = None

        if self.sub_face_name:
            self.destroy_subscription(self.sub_face_name)
            self.sub_face_name = None

        if self.sub_face_question:
            self.destroy_subscription(self.sub_face_question)
            self.sub_face_question = None

        if self.sub_face_timeout:
            self.destroy_subscription(self.sub_face_timeout)
            self.sub_face_timeout = None

        if self.sub_recognitions:
            self.destroy_subscription(self.sub_recognitions)
            self.sub_recognitions = None

        return super().on_deactivate(state)

    def recognitions_callback(self, msg: FaceRecognitionArray):
        self.face_recognitions_queue.put(msg)

    def face_name_response_callback(self, msg: FaceNameResponse):
        self.face_name_queue.put(msg.name)

    def face_question_response_callback(self, msg: FaceQuestionResponse):
        self.face_question_queue.put(msg.answer)

    def face_timeout_response_callback(self, _: Empty):
        self.face_timeout_response = True


class HumanFaceManager:

    LOWER_BOUND = 0.75 # Poner como variables globales en un archivo a parte en este paquete o en este mismo archivo e importarlas en los nodos que las usen
    MIDDLE_BOUND = 0.80
    UPPER_BOUND = 0.90

    def __init__(self, node: HumanFaceManagerLifecycleNode, ask_unknowns=True, draw_rectangle=True, show_distance=True, show_score=True):
        self.ask_unknowns = ask_unknowns
        self.draw_rectangle = draw_rectangle
        self.show_distance = show_distance
        self.show_score = show_score

        self.last_frame = None
        self.gui_request_sent_info = None

        self.node = node
        self.people = PeopleManager(self.node)

    def spin(self):
        if not self.node.face_recognitions_queue.empty():
            recognition_msg = self.node.face_recognitions_queue.get()
            self.process_recognitions(recognition_msg)

        if not self.node.face_name_queue.empty():
            name = self.node.face_name_queue.get()
            self.process_face_name_response(name)

        if not self.node.face_question_queue.empty():
            answer = self.node.face_question_queue.get()
            self.process_face_question_response(answer)
        
        if self.node.face_timeout_response:
            self.node.face_timeout_response = False
            self.gui_request_sent_info = None

    def process_recognitions(self, msg):
        frame = self.node.bridge.imgmsg_to_cv2(msg.image, "bgr8")
        self.last_frame = frame

        for det, recog in zip(msg.detections, msg.recognitions):
            classified_id = recog.classified_id
            classified_name = recog.classified_name
            features = recog.features
            distance = recog.distance
            pos = recog.pos
            score = det.confidence
            face_updated = recog.face_updated
            face_aligned = self.node.bridge.imgmsg_to_cv2(recog.face_aligned, "bgr8")

            if face_updated:
                log_message = f"Se ha actualizado la imagen de la cara con id {classified_id}"
                metadata_json = json.dumps({"faceprint_id": classified_id})
                self.create_log(CONSTANTS.ACTION.UPDATE_FACE, classified_id, log_message, metadata_json)

            if distance < self.LOWER_BOUND: # No sabe quien es (en teoria nunca lo ha visto), pregunta por el nombre
                classified_name = None
                classified_id = None

                if score >= 1 and self.ask_unknowns: # Si la imagen es buena, pregunta por el nombre, para que no coja una imagen mala
                    if not self.gui_request_sent_info: # Si no hay ninguna cosa enviada
                        face_aligned_base64 = self.node.bridge.cv2_to_base64(face_aligned)
                        if self.gui_request("get_name", json.dumps({"image": face_aligned_base64})):
                            self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                            self.read_text("¿Cual es tu nombre?", asking_mode="get_name")
                        else:
                            self.node.get_logger().info("Error al enviar una petición de nombre a la GUI")

            elif distance < self.MIDDLE_BOUND: # Cree que es alguien, pide confirmacion
                if score >= 1 and self.ask_unknowns: # Pero solo si la foto es buena
                    if not self.gui_request_sent_info:
                        face_aligned_base64 = self.node.bridge.cv2_to_base64(face_aligned)
                        if self.gui_request("ask_if_name", json.dumps({"image": face_aligned_base64, "name": classified_name})):
                            self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                            self.read_text(f"Creo que eres {classified_name}, ¿es cierto?", asking_mode="confirm_name")
                        else:
                            self.node.get_logger().info("Error al enviar una petición de preguntar nombre a la GUI")

            elif distance < self.UPPER_BOUND: # Sabe que es alguien pero lo detecta un poco raro
                self.people.process_detection(classified_id, score, distance)
            else: # Reconoce perfectamente
                if self.people.get_last_seen(classified_id) > 60:
                    self.read_text("Bienvenido de vuelta " + classified_name)

                self.people.process_detection(classified_id, score, distance)

                output, message = self.training_request(String(data="refine_class"), String(data=json.dumps({
                    "class_id": classified_id,
                    "features": features,
                    "position": pos
                }))) # Refinamos la clase

                if output < 0:
                    self.node.get_logger().info(f">> ERROR: Al refinar una clase: {message}")

            mark_face(frame, [det.corner.x, det.corner.y, det.width, det.height], distance, self.MIDDLE_BOUND, self.UPPER_BOUND, classified=classified_name, 
                      drawRectangle=self.draw_rectangle, score=score, showDistance=self.show_distance, showScore=self.show_score) # TODO: mover a recognizer

        actual_people_time = self.people.get_all_last_seen()
        actual_people_json = json.dumps(actual_people_time)

        self.node.pub_people.publish(String(data=actual_people_json))
        self.node.pub_recognition.publish(self.node.bridge.cv2_to_imgmsg(frame, "bgr8"))

    def process_face_name_response(self, name):
        [_, _, face_aligned_base64, features, score, _] = self.gui_request_sent_info
        self.gui_request_sent_info = None

        result, message = self.training_request(String(data="add_class"), String(data=json.dumps({
            "class_name": name,
            "features": features,
            "face": face_aligned_base64,
            "score": score
        })))

        if result >= 0:
            distance = 1
            classified_id = message

            self.node.get_logger().info(f"Nueva clase con id {classified_id}")
            self.people.process_detection(classified_id, score, distance)

            self.read_text("Bienvenido " + name + ", no te conocía")

            log_message = f"Se ha creado una nueva clase con id {classified_id}"
            metadata_json = json.dumps({"faceprint_id": classified_id, "name": name, "face_score": score})
            self.create_log(CONSTANTS.ACTION.ADD_CLASS, classified_id, log_message, metadata_json)
        else:
            self.node.get_logger().info(f">> ERROR: Algo salio mal al agregar una nueva clase: {message}")

    def process_face_question_response(self, answer):
        [classified_id, classified_name, face_aligned_base64, features, score, distance] = self.gui_request_sent_info
        self.gui_request_sent_info = None

        if answer:
            self.people.process_detection(classified_id, score, distance)
            output, message = self.training_request(String(data="add_features"), String(data=json.dumps({
                "class_id": classified_id,
                "features": features,
            })))

            self.node.get_logger().info(message)

            if output >= 0:
                self.read_text("Gracias " + classified_name + ", me gusta confirmar que estoy reconociendo bien")

                log_message = f"Se ha añadido un nuevo vector de características independiente a la clase {classified_id}"
                metadata_json = json.dumps({"faceprint_id": classified_id})
                self.create_log(CONSTANTS.ACTION.ADD_FEATURES, classified_id, log_message, metadata_json)
            else:
                self.node.get_logger().info(f">> ERROR: Algo salio mal al agregar features a una clase")
        else:
            if self.gui_request("get_name", json.dumps({"image": face_aligned_base64})):
                self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                self.read_text("Entonces, ¿Cual es tu nombre?", asking_mode="get_name")

    def training_request(self, cmd_type_msg, args_msg):
        training_request = Training.Request()
        training_request.cmd_type = cmd_type_msg
        training_request.args = args_msg

        future_training = self.node.training_client.call_async(training_request)
        rclpy.spin_until_future_complete(self.node, future_training)
        result_training = future_training.result()

        return result_training.result, result_training.message.data

    def gui_request(self, mode, data_json):
        req = TriggerUserInteraction.Request()
        req.mode = mode
        req.data_json = data_json

        future = self.node.gui_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        result = future.result()

        return result.accepted

    def get_actual_people_service(self, request, response):
        actual_people_time = self.people.get_all_last_seen()
        response.text = json.dumps(actual_people_time)
        return response

    def get_last_frame_service(self, request, response):
        response.text = self.node.bridge.cv2_to_base64(self.last_frame, quality=100)
        return response

    def read_text(self, text, asking_mode=""):
        self.node.get_logger().info(f"[SANCHO] {text}")
        self.node.pub_input_tts.publish(String(data=json.dumps({
            "text": text,
            "asking_mode": asking_mode
        })))

    def create_log(self, action, faceprint_id, message="", metadata_json=""):
        self.node.pub_log.publish(Log(
            level=CONSTANTS.LEVEL.INFO,
            origin=CONSTANTS.ORIGIN.ROS,
            actor="logic_node",
            action=action,
            target=faceprint_id,
            message=message,
            metadata_json=metadata_json
        ))


def main(args=None):
    rclpy.init(args=args)

    lifecycle_node = HumanFaceManagerLifecycleNode()

    rclpy.spin(lifecycle_node)
    rclpy.shutdown()
