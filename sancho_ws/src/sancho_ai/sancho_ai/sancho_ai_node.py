import json
import rclpy
import threading

from rclpy.node import Node
from enum import Enum

from hri_msgs.srv import SanchoPrompt

from .log_manager import LogManager
from .memory_manager import MemoryManager
from .ais import create_sancho_ai, AIType, LLMTaskAI

class MODE(int, Enum):
    NORMAL = 0

    GET_NAME = 1
    CONFIRM_NAME = 2

    NO_ONE_KNOWN = 3
    SOME_KNOWN = 4
    ALL_KNOWN = 5


class SanchoAINode(Node):

    MODE_TASK = {
        MODE.GET_NAME: LLMTaskAI.get_name,
        MODE.CONFIRM_NAME: LLMTaskAI.confirm_name,
        MODE.NO_ONE_KNOWN: LLMTaskAI.no_one_known,
        MODE.SOME_KNOWN: LLMTaskAI.some_known,
        MODE.ALL_KNOWN: LLMTaskAI.all_known
    }

    def __init__(self, ai_type):
        super().__init__("sancho_ai")

        self.ai_type = ai_type
        self.sancho_ai = create_sancho_ai(self.ai_type)
        self.memory_manager = MemoryManager()
        self.chats = {}

        self.prompt_serv = self.create_service(SanchoPrompt, "sancho_ai/prompt", self.prompt_service)

        LLMTaskAI.init(self)
        LogManager.init(self)

        self.get_logger().info("SanchoAI Node initializated successfully")

    def prompt_service(self, request, response):
        try:
            mode = MODE(request.mode)
        except ValueError:
            self.get_logger().error(f"Sancho prompt with unknown mode: {request.mode}")
            response.value_json = json.dumps({"error": "Unknown Mode"})
            return response

        if mode == MODE.NORMAL:
            self.get_logger().info("Normal Sancho Prompt")
            args = json.loads(request.args_json)
            return self.normal_message(response, request.chat_id, request.text, args["user_id"], args["user_name"])
        
        elif mode in self.MODE_TASK:
            self.get_logger().info(f"{mode.name} Sancho Prompt")
            return self.task_message(response, request.text, self.MODE_TASK[mode])
        
        else:
            self.get_logger().error(f"Sancho prompt with mode that has no associated task: {mode}")
            response.value_json = json.dumps({"error": "Unsupported Mode"})
            return response

    def normal_message(self, response, chat_id, text, user_id, user_name):
        chat_history = self.chats.get(chat_id, [])
        value, intent, arguments, provider, model = self.sancho_ai.on_message(text, chat_history)

        chat_history.append({"role": "user", "content": text})
        chat_history.append({"role": "assistant", "content": json.dumps({"response": value["text"], "emotion": value["emotion"]})})
        self.chats[chat_id] = chat_history[-20:] # últimos 10 turnos (20 mensajes)

        response.value_json = json.dumps(value)
        response.method = self.type
        response.intent = intent
        response.args_json = json.dumps(arguments)
        response.provider = provider
        response.model = model

        chat = list(self.chats[chat_id])
        threading.Thread(target=self.memory_manager.update_memory, args=(user_id, chat), daemon=True).start()

        return response

    def task_message(self, response, text, task_method):
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