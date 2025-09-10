import json
from queue import Queue

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Empty
from hri_msgs.srv import Training, TriggerUserInteraction
from hri_msgs.msg import Log, FaceNameResponse, FaceQuestionResponse
from rumi_msgs.msg import SessionMessage
from sancho_msgs.msg import FaceRecognitionArray

from sancho_web_assistant.database.system_database import CONSTANTS
from .database.people_manager import PeopleManager
from .api.gui_utils import mark_face
from .hri_bridge import HRIBridge


class HumanFaceManagerLifecycleNode(Node):

    def __init__(self):
        super().__init__('human_face_manager')

        self.face_recognitions_queue = Queue()
        self.face_name_queue = Queue()
        self.face_question_queue = Queue()
        self.face_timeout_response = False

        self.face_name_response_sub = self.create_subscription(FaceNameResponse, 'gui/face_name_response', self.face_name_response_callback, 10)
        self.face_question_response_sub = self.create_subscription(FaceQuestionResponse, 'gui/face_question_response', self.face_question_response_callback, 10)
        self.face_timeout_response_sub = self.create_subscription(Empty, 'gui/face_timeout_response', self.face_timeout_response_callback, 10)
        self.subscription_recognitions = self.create_subscription(FaceRecognitionArray, '/face_recognitions', self.recognitions_callback, 1)

        self.publisher_log = self.create_publisher(Log, 'logs/add', 10)
        self.publisher_session = self.create_publisher(SessionMessage, 'rumi/sessions/process', 10)
        self.publisher_recognition = self.create_publisher(String, 'camera/color/recognition', 1)
        self.publisher_people = self.create_publisher(String, 'logic/info/actual_people', 1)
        self.input_tts = self.create_publisher(String, 'input_tts', 10)

        self.training_client = self.create_client(Training, 'recognition/training')
        while not self.training_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Training service not available, waiting again...')

        self.gui_client = self.create_client(TriggerUserInteraction, 'gui/request')
        while not self.gui_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('GUI service not available, waiting again...')

        self.br = HRIBridge()
        self.get_logger().info("HRI Logic Node initialized successfully (refactored)")

    def recognitions_callback(self, msg):
        self.face_recognitions_queue.put(msg)

    def face_name_response_callback(self, msg):
        self.face_name_queue.put(msg.name)

    def face_question_response_callback(self, msg):
        self.face_question_queue.put(msg.answer)

    def face_timeout_response_callback(self, _):
        self.face_timeout_response = True


class HumanFaceManager:

    LOWER_BOUND = 0.75 # Poner como variables globales en un archivo a parte en este paquete o en este mismo archivo e importarlas en los nodos que las usen
    MIDDLE_BOUND = 0.80
    UPPER_BOUND = 0.90

    def __init__(self, ask_unknowns=True, draw_rectangle=True, show_distance=True, show_score=True):
        self.ask_unknowns = ask_unknowns
        self.draw_rectangle = draw_rectangle
        self.show_distance = show_distance
        self.show_score = show_score

        self.last_frame = None
        self.gui_request_sent_info = None

        self.node = HumanFaceManagerLifecycleNode(self)
        self.people = PeopleManager(self.node)

    def spin(self):
        while rclpy.ok():
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

            rclpy.spin_once(self.node)

    def process_recognitions(self, msg):
        frame = self.node.br.imgmsg_to_cv2(msg.image, "bgr8")
        self.last_frame = frame

        for det, recog in zip(msg.detections, msg.recognitions):
            classified_id = recog.classified_id
            classified_name = recog.classified_name
            features = recog.features
            distance = recog.distance
            pos = recog.pos
            score = det.confidence
            face_updated = recog.face_updated
            face_aligned = self.node.br.imgmsg_to_cv2(recog.face_aligned, "bgr8")

            if face_updated:
                log_message = f"Se ha actualizado la imagen de la cara con id {classified_id}"
                metadata_json = json.dumps({"faceprint_id": classified_id})
                self.create_log(CONSTANTS.ACTION.UPDATE_FACE, classified_id, log_message, metadata_json)

            if distance < self.LOWER_BOUND: # No sabe quien es (en teoria nunca lo ha visto), pregunta por el nombre
                classified_name = None
                classified_id = None

                if score >= 1 and self.ask_unknowns: # Si la imagen es buena, pregunta por el nombre, para que no coja una imagen mala
                    if not self.gui_request_sent_info: # Si no hay ninguna cosa enviada
                        face_aligned_base64 = self.node.br.cv2_to_base64(face_aligned)
                        if self.gui_request("get_name", json.dumps({"image": face_aligned_base64})):
                            self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                            self.read_text("¿Cual es tu nombre?", asking_mode="get_name")
                        else:
                            self.node.get_logger().info("Error al enviar una petición de nombre a la GUI")

            elif distance < self.MIDDLE_BOUND: # Cree que es alguien, pide confirmacion
                if score >= 1 and self.ask_unknowns: # Pero solo si la foto es buena
                    if not self.gui_request_sent_info:
                        face_aligned_base64 = self.node.br.cv2_to_base64(face_aligned)
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

        self.node.publisher_people.publish(String(data=actual_people_json))
        self.node.publisher_recognition.publish(self.node.br.cv2_to_imgmsg(frame, "bgr8"))

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
        response.text = self.node.br.cv2_to_base64(self.last_frame, quality=100)
        return response

    def read_text(self, text, asking_mode=""):
        self.node.get_logger().info(f"[SANCHO] {text}")
        self.node.input_tts.publish(String(data=json.dumps({
            "text": text,
            "asking_mode": asking_mode
        })))

    def create_log(self, action, faceprint_id, message="", metadata_json=""):
        self.node.publisher_log.publish(Log(
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
