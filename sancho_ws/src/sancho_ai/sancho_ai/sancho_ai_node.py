import json
import rclpy
from rclpy.node import Node
from enum import Enum

from hri_msgs.srv import SanchoPrompt

from .log_manager import LogManager
from .ais import create_sancho_ai, AIType, LLMTaskAI

class MODE(int, Enum):
    NORMAL = 0

    GET_NAME = 1
    CONFIRM_NAME = 2

    NO_ONE_KNOWN = 3
    SOME_KNOWN = 4
    ALL_KNOWN = 5


class SanchoAINode(Node):

    def __init__(self, type):
        super().__init__("sancho_ai")

        self.type = type
        self.sancho_ai = create_sancho_ai(self.type)
        self.task_ai = LLMTaskAI()

        self.prompt_serv = self.create_service(SanchoPrompt, "sancho_ai/prompt", self.prompt_service)

        self.chats = {}

        LogManager.set_node(self)
        self.get_logger().info("SanchoAI Node initializated successfully")

    def prompt_service(self, request, response):
        if request.mode == MODE.NORMAL:
            self.get_logger().info("Normal Sancho Prompt")

            args = json.loads(request.args_json)
            user_id = args["user_id"]
            user_name = args["user_name"]

            return self.normal_message(response, request.chat_id, request.text, user_id, user_name)
        
        elif request.mode == MODE.GET_NAME:
            self.get_logger().info("Get Name Sancho Prompt")
            return self.get_name_message(response, request.text)
        
        elif request.mode == MODE.CONFIRM_NAME:
            self.get_logger().info("Confirm Name Sancho Prompt")
            return self.confirm_name_message(response, request.text)
        
        elif request.mode == MODE.NO_ONE_KNOWN:
            self.get_logger().info("No One Known Sancho Prompt")
            return self.no_one_known_message(response, request.text)
        
        elif request.mode == MODE.SOME_KNOWN:
            self.get_logger().info("Some Known Sancho Prompt")
            return self.some_known_message(response, request.text)
        
        elif request.mode == MODE.ALL_KNOWN:
            self.get_logger().info("All Known Sancho Prompt")
            return self.all_known_message(response, request.text)

        else:
            self.get_logger().error(f"Sancho prompt with unknown task mode: {request.mode}")

    def normal_message(self, response, chat_id, text, user_id, user_name):
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
        return self._task_message(response, text, self.task_ai.get_name)
    
    def confirm_name_message(self, response, text):
        return self._task_message(response, text, self.task_ai.confirm_name)
    
    def no_one_known_message(self, response, text):
        return self._task_message(response, text, self.task_ai.no_one_known)
    
    def some_known_message(self, response, text):
        return self._task_message(response, text, self.task_ai.some_known)
    
    def all_known_message(self, response, text):
        return self._task_message(response, text, self.task_ai.all_known)  
    
    def _task_message(self, response, text, task_method):
        value, provider, model = task_method(text)

        response.value_json = json.dumps(value)
        response.provider = provider
        response.model = model

        return response

def main(args=None):
    rclpy.init(args=args)

    node = SanchoAINode(AIType.LLM_CLASSIFIER_GENERATOR)

    rclpy.spin(node)
    rclpy.shutdown()