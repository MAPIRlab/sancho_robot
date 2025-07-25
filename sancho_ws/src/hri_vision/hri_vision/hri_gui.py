import json
import rclpy
import base64
import threading

from rclpy.node import Node
from rclpy.timer import Timer
from std_msgs.msg import Empty, String, Bool

from hri_msgs.msg import FaceNameResponse, FaceQuestionResponse
from hri_msgs.srv import TriggerUserInteraction

from .gui import AppController

def encode_image_base64(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


class HRIGUINode(Node):
    def __init__(self, hri_gui: 'HRIGUI'):
        super().__init__("hri_gui")

        self.hri_gui = hri_gui

        self.face_name_pub = self.create_publisher(FaceNameResponse, 'gui/face_name_response', 10)
        self.face_question_pub = self.create_publisher(FaceQuestionResponse, 'gui/face_question_response', 10)
        self.face_timeout_pub = self.create_publisher(Empty, 'gui/face_timeout_response', 10)

        self.name_answer_sub = self.create_subscription(String, "gui/name_answer", self.name_answer_callback, 10)
        self.confirm_name_sub = self.create_subscription(Bool, "gui/confirm_name", self.confirm_name_callback, 10)

        self.trigger_interaction_srv = self.create_service(TriggerUserInteraction, 'gui/request', self.hri_gui.user_interaction_service)

    def name_answer_callback(self, msg):
        name = str(msg.data)
        
        self.hri_gui.send_face_name_response(name)
        self.hri_gui.controller.set_mode_normal()

    def confirm_name_callback(self, msg):
        answer = bool(msg.data)
        
        self.hri_gui.send_face_question_response(answer)
        self.hri_gui.controller.set_mode_normal()

class HRIGUI:
    def __init__(self):
        self.controller = AppController(self.send_face_name_response, self.send_face_question_response)
        self.node = HRIGUINode(self)
        self.timeout_timer: Timer | None = None

        self.ros_thread = threading.Thread(target=lambda: rclpy.spin(self.node), daemon=True)
        self.ros_thread.start()

    def spin(self):
        self.controller.start()

    def send_face_name_response(self, name):
        self.stop_timeout()
        self.node.face_name_pub.publish(FaceNameResponse(name=name))

    def send_face_question_response(self, answer):
        self.stop_timeout()
        self.node.face_question_pub.publish(FaceQuestionResponse(answer=answer))

    def send_face_timeout_response(self):
        self.node.face_timeout_pub.publish(Empty())

    def user_interaction_service(self, request, response):
        mode = request.mode
        data = json.loads(request.data_json)

        if mode == "get_name":
            image_base64 = data["image"]

            response.accepted = self.controller.set_mode_get_name(image_base64)
            self.start_timeout(300)
        elif mode == "ask_if_name":
            image_base64 = data["image"]
            name = data["name"]
            
            response.accepted = self.controller.set_mode_ask_if_name(image_base64, name)
            self.start_timeout(300)
        elif mode == "show_photo":
            image_base64 = data["image"]

            response.accepted = self.controller.set_mode_show_photo(image_base64)
            self.start_timeout(5)
        else:
            self.node.get_logger().info(f"Pantalla no reconocida: {mode}")
            response.accepted = False

        return response

    def start_timeout(self, seconds: float):
        self.stop_timeout()
        self.node.get_logger().info(f"Iniciando timeout de {seconds} segundos...")
        self.timeout_timer = self.node.create_timer(seconds, lambda: self.handle_timeout(seconds))

    def stop_timeout(self):
        if self.timeout_timer is not None:
            self.node.get_logger().info("Cancelando timeout anterior.")
            self.timeout_timer.cancel()
            self.node.destroy_timer(self.timeout_timer)
            self.timeout_timer = None
    
    def handle_timeout(self, seconds):
        self.node.get_logger().info(f"[{self.controller.model.mode}] Timeout after {seconds}s")
        if self.controller.model.mode in ["get_name", "ask_if_name"]:
            self.send_face_timeout_response()
            
        self.controller.set_mode_normal()

def main(args=None):
    rclpy.init(args=args)

    hri_gui = HRIGUI()
    hri_gui.spin()

    rclpy.shutdown()
