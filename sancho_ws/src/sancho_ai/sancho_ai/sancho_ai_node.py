import json
import rclpy
from rclpy.node import Node

from hri_msgs.srv import SanchoPrompt

from .log_manager import LogManager
from .ais import create_sancho_ai, AIType, LLMAskingAI


class SanchoAINode(Node):

    def __init__(self, type):
        super().__init__("sancho_ai")

        self.type = type
        self.sancho_ai = create_sancho_ai(self.type)
        self.asking_ai = LLMAskingAI()

        self.prompt_serv = self.create_service(SanchoPrompt, "sancho_ai/prompt", self.prompt_service)

        self.chats = {}

        LogManager.set_node(self)
        self.get_logger().info("SanchoAI Node initializated successfully")

    def prompt_service(self, request, response):
        if not request.asking_mode:
            self.get_logger().info("Normal Sancho Prompt")
            return self.normal_message(response, request.chat_id, request.text)
        
        elif request.asking_mode == "get_name":
            self.get_logger().info("Get Name Sancho Prompt")
            return self.get_name_message(response, request.text)
        
        elif request.asking_mode == "confirm_name":
            self.get_logger().info("Confirm Name Sancho prPromptompt")
            return self.confirm_name_message(response, request.text)
        
        else:
            self.get_logger().error(f"Sancho prompt with unknown asking mode: {request.asking_mode}")

    def normal_message(self, response, chat_id, text):
        chat_history = self.chats.get(chat_id, [])

        value, intent, arguments, provider, model = self.sancho_ai.on_message(text, chat_history)
        
        chat_history.append({"role": "user", "content": text})
        chat_history.append({"role": "assistant", "content": json.dumps({"response": value["text"], "emotion": value["emotion"]}) })

        self.chats[chat_id] = chat_history[-20:]  # 10 turnos

        response.value_json = json.dumps(value)
        response.method = self.type
        response.intent = intent
        response.args_json = json.dumps(arguments)
        response.provider = provider
        response.model = model

        return response

    def get_name_message(self, response, text):
        value, provider, model = self.asking_ai.get_name(text)

        response.value_json = json.dumps(value)
        response.provider = provider
        response.model = model

        return response

    def confirm_name_message(self, response, text):
        value, provider, model = self.asking_ai.confirm_name(text)

        response.value_json = json.dumps(value)
        response.provider = provider
        response.model = model

        return response

def main(args=None):
    rclpy.init(args=args)

    node = SanchoAINode(AIType.LLM_CLASSIFIER_GENERATOR)

    rclpy.spin(node)
    rclpy.shutdown()