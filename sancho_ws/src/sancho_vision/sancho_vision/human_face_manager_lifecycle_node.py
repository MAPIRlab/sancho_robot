import json
import time
import threading
from queue import Queue

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Empty
from std_srvs.srv import SetBool, Empty as EmptySrv
from sancho_interfaces.srv import Training, TriggerUserInteraction
from sancho_interfaces.msg import Log, FaceNameResponse, FaceQuestionResponse
from sancho_interfaces.msg import SessionMessage
from sancho_interfaces.msg import FaceRecognitionArray, InputTTS
from sancho_interfaces.srv import AskUser

from sancho_web_assistant.database.system_database import CONSTANTS
from sancho_audio.assistant_node import QUESTION
from .database.people_manager import PeopleManager
from .hri_bridge import HRIBridge


def _call_service_sync(node, client, request, timeout=5.0):
    if not client.service_is_ready():
        raise RuntimeError(f"Service {client.srv_name} is not ready")

    fut = client.call_async(request)
    done = threading.Event()

    def _on_done(_):
        try:
            _ = fut.result()
        except Exception:
            pass
        finally:
            done.set()

    fut.add_done_callback(_on_done)

    deadline = time.monotonic() + timeout if timeout else None
    while True:
        if done.wait(timeout=0.01):
            return fut.result()
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError(f"Timeout waiting for service {client.srv_name} response")


class HumanFaceManagerLifecycleNode(LifecycleNode):
    def __init__(self):
        super().__init__("human_face_manager")
        
        self.human_face_manager = HumanFaceManager(self)

        self.declare_parameters(namespace="", parameters=[
            ("face_recognitions_topic", "/face_recognitions"),
            ("gui_face_name_response_topic", "/gui/face_name_response"),
            ("gui_face_question_response_topic", "/gui/face_question_response"),
            ("gui_face_timeout_response_topic", "/gui/face_timeout_response"),
            ("logs_topic", "/logs/add"),
            ("people_topic", "/logic/info/actual_people"),
            ("sessions_topic", "/rumi/sessions/process"),
            ("input_tts_topic", "/input_tts"),
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
        self.pub_people = None
        self.pub_session = None
        self.pub_input_tts = None

        self.training_client = None
        self.gui_client = None
        self.clear_no_name_client = None
        self.set_learn_without_name_client = None
        self.ask_user_client = None

        # ¡Reentrante para permitir concurrencia entre callbacks!
        self.cb_group = ReentrantCallbackGroup()

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo manejador de rostros...")

        self.face_recognitions_topic = self.get_parameter("face_recognitions_topic").value
        self.gui_face_name_response_topic = self.get_parameter("gui_face_name_response_topic").value
        self.gui_face_question_response_topic = self.get_parameter("gui_face_question_response_topic").value
        self.gui_face_timeout_response_topic = self.get_parameter("gui_face_timeout_response_topic").value
        self.logs_topic = self.get_parameter("logs_topic").value
        self.people_topic = self.get_parameter("people_topic").value
        self.sessions_topic = self.get_parameter("sessions_topic").value
        self.input_tts_topic = self.get_parameter("input_tts_topic").value
        self.processing_rate = float(self.get_parameter("processing_rate").value)
        self.service_wait_attempts = int(self.get_parameter("service_wait_attempts").value)
        self.service_wait_timeout_sec = float(self.get_parameter("service_wait_timeout_sec").value)

        qos10 = QoSProfile(depth=10)
        qos1 = QoSProfile(depth=1)
        self.pub_log = self.create_lifecycle_publisher(Log, self.logs_topic, qos10)
        self.pub_people = self.create_lifecycle_publisher(String, self.people_topic, qos1)
        self.pub_session = self.create_lifecycle_publisher(SessionMessage, self.sessions_topic, qos10)
        self.pub_input_tts = self.create_lifecycle_publisher(InputTTS, self.input_tts_topic, qos10)

        self.ask_user_client = self.create_client(AskUser, 'sancho_audio/ask_user', callback_group=self.cb_group)
        self.training_client = self.create_client(Training, "recognition/training", callback_group=self.cb_group)
        while not self.training_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Training service not available, waiting again...')

        self.gui_client = self.create_client(TriggerUserInteraction, "gui/request", callback_group=self.cb_group)
        while not self.gui_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('GUI service not available, waiting again...')

        self.clear_no_name_client = self.create_client(EmptySrv, "recognition/clear_no_name", callback_group=self.cb_group)
        while not self.clear_no_name_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Clear no name service not available, waiting again...")

        self.set_learn_without_name_client = self.create_client(SetBool, "recognition/set_learn_without_name", callback_group=self.cb_group)
        while not self.set_learn_without_name_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info("Set learn without name service not available, waiting again...")

        return super().on_configure(state)

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo manejador de rostros...")

        qos10 = QoSProfile(depth=10)
        qos1 = QoSProfile(depth=1)
        self.sub_face_name = self.create_subscription(
            FaceNameResponse, 
            self.gui_face_name_response_topic, 
            self.face_name_response_callback, 
            qos10, 
            callback_group=self.cb_group
        )
        self.sub_face_question = self.create_subscription(
            FaceQuestionResponse, 
            self.gui_face_question_response_topic, 
            self.face_question_response_callback, 
            qos10, 
            callback_group=self.cb_group
        )
        self.sub_face_timeout = self.create_subscription(
            Empty, 
            self.gui_face_timeout_response_topic, 
            self.face_timeout_response_callback, 
            qos10, 
            callback_group=self.cb_group
        )

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.sub_recognitions = self.create_subscription(
            FaceRecognitionArray, 
            self.face_recognitions_topic, 
            self.recognitions_callback, 
            qos, 
            callback_group=self.cb_group
        )

        self.face_timeout_response = False
        self.spin_timer = self.create_timer(1.0 / self.processing_rate, self.human_face_manager.spin, callback_group=self.cb_group)

        try:
            learn_future = self.set_learn_without_name_client.call_async(SetBool.Request(data=False))
            learn_future.add_done_callback(lambda _: self.get_logger().info("Set learn without name a False completado correctamente."))

            clear_future = self.clear_no_name_client.call_async(EmptySrv.Request())
            clear_future.add_done_callback(lambda _: self.get_logger().info("Clear no name completado correctamente."))

            self.get_logger().info("Llamadas a servicios clear no name y set learn without name iniciadas.")    
        except Exception as e:
            self.get_logger().error(f"Error al llamar al servicio clear no name: {e}")

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

        try:
            learn_future = self.set_learn_without_name_client.call_async(SetBool.Request(data=True))
            learn_future.add_done_callback(lambda _: self.get_logger().info("Set learn without name a True completado correctamente."))

            self.get_logger().info("Llamadas a servicios clear no name y set learn without name iniciadas.")    
        except Exception as e:
            self.get_logger().error(f"Error al llamar al servicio clear no name: {e}")

        return super().on_deactivate(state)

    def recognitions_callback(self, msg: FaceRecognitionArray):
        self.get_logger().info("recibidooo")
        self.face_recognitions_queue.put(msg)

    def face_name_response_callback(self, msg: FaceNameResponse):
        self.face_name_queue.put(msg.name)

    def face_question_response_callback(self, msg: FaceQuestionResponse):
        self.face_question_queue.put(msg.answer)

    def face_timeout_response_callback(self, _: Empty):
        self.face_timeout_response = True


class HumanFaceManager:

    LOWER_BOUND = 0.75
    MIDDLE_BOUND = 0.80
    UPPER_BOUND = 0.90

    DETECTOR_BOUND = 1.0

    def __init__(self, node: HumanFaceManagerLifecycleNode, ask_unknowns=True, draw_rectangle=True, show_distance=True, show_score=True):
        self.ask_unknowns = ask_unknowns
        self.draw_rectangle = draw_rectangle
        self.show_distance = show_distance
        self.show_score = show_score

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
        for det, recog in zip(msg.detections, msg.recognitions):
            classified_id = recog.classified_id
            classified_name = recog.classified_name
            features = [float(f) for f in recog.features]
            distance = recog.distance
            pos = recog.pos
            score = det.confidence
            face_updated = recog.face_updated
            face_aligned = self.node.bridge.imgmsg_to_cv2(recog.face_aligned, "bgr8")

            if face_updated:
                log_message = f"Se ha actualizado la imagen de la cara con id {classified_id}"
                metadata_json = json.dumps({"faceprint_id": classified_id})
                self.create_log(CONSTANTS.ACTION.UPDATE_FACE, classified_id, log_message, metadata_json)

            if distance < self.LOWER_BOUND:  # Desconocido → pedir nombre
                classified_id = None
                classified_name = None

                if score >= self.DETECTOR_BOUND and self.ask_unknowns:
                    if not self.gui_request_sent_info:
                        face_aligned_base64 = self.node.bridge.cv2_to_base64(face_aligned)
                        if self.gui_request("get_name", json.dumps({"image": face_aligned_base64})):
                            self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                            self.ask_user(QUESTION.GET_NAME)
                        else:
                            self.node.get_logger().info("Error al enviar una petición de nombre a la GUI")

            elif distance < self.MIDDLE_BOUND:  # Probable → confirmar
                if score >= self.DETECTOR_BOUND and self.ask_unknowns:
                    if not self.gui_request_sent_info:
                        face_aligned_base64 = self.node.bridge.cv2_to_base64(face_aligned)
                        if self.gui_request("ask_if_name", json.dumps({"image": face_aligned_base64, "name": classified_name})):
                            self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                            self.ask_user(QUESTION.CONFIRM_NAME, args_json=json.dumps({"name": classified_name}))
                        else:
                            self.node.get_logger().info("Error al enviar una petición de preguntar nombre a la GUI")

            elif distance < self.UPPER_BOUND:  # Reconoce con duda
                self.people.process_detection(classified_id, score, distance)
            else:  # Reconoce con seguridad
                if self.people.get_last_seen(classified_id) > 60:
                    self.read_text("Bienvenido de vuelta " + classified_name, "happy")
                self.people.process_detection(classified_id, score, distance)

        actual_people_time = self.people.get_all_last_seen()
        actual_people_json = json.dumps(actual_people_time)

        self.node.pub_people.publish(String(data=actual_people_json))

    def process_face_name_response(self, name):
        [_, _, face_aligned_base64, features, score, _] = self.gui_request_sent_info
        self.gui_request_sent_info = None

        result, message = self.training_request(
            String(data="add_class"),
            String(data=json.dumps({
                "class_name": name,
                "features": features,
                "face": face_aligned_base64,
                "score": score
            }))
        )

        if result >= 0:
            distance = 1
            classified_id = message

            self.node.get_logger().info(f"Nueva clase con id {classified_id}")
            self.people.process_detection(classified_id, score, distance)

            self.read_text("Bienvenido " + name + ", no te conocía", "happy")

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
            output, message = self.training_request(
                String(data="add_features"),
                String(data=json.dumps({
                    "class_id": classified_id,
                    "features": features,
                }))
            )

            if output >= 0:
                self.read_text("Gracias " + classified_name + ", me gusta confirmar que estoy reconociendo bien", "happy")

                log_message = f"Se ha añadido un nuevo vector de características independiente a la clase {classified_id}"
                metadata_json = json.dumps({"faceprint_id": classified_id})
                self.create_log(CONSTANTS.ACTION.ADD_FEATURES, classified_id, log_message, metadata_json)
            else:
                self.node.get_logger().info(f">> ERROR: Algo salio mal al agregar features a una clase")
        else:
            if self.gui_request("get_name", json.dumps({"image": face_aligned_base64})):
                self.gui_request_sent_info = [classified_id, classified_name, face_aligned_base64, features, score, distance]
                self.ask_user(QUESTION.GET_NAME)

    def training_request(self, cmd_type_msg, args_msg):
        req = Training.Request()
        req.cmd_type = cmd_type_msg
        req.args = args_msg

        resp = _call_service_sync(self.node, self.node.training_client, req, timeout=10.0)
        return resp.result, resp.message.data

    def gui_request(self, mode, data_json):
        req = TriggerUserInteraction.Request()
        req.mode = mode
        req.data_json = data_json

        result = _call_service_sync(self.node, self.node.gui_client, req, timeout=10.0)
        return result.accepted

    def ask_user(self, question_id, args_json=""):
        if not self.node.ask_user_client.service_is_ready():
            return False
        
        req = AskUser.Request()
        req.question_id = question_id
        req.args_json = args_json

        result = _call_service_sync(self.node, self.node.ask_user_client, req, timeout=10.0)
        return result.accepted

    def read_text(self, text, emotion="neutral"):
        self.node.get_logger().info(f"[SANCHO] {text}")
        self.node.pub_input_tts.publish(InputTTS(text=text, emotion=emotion))

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
    node = HumanFaceManagerLifecycleNode()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
