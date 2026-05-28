import json
import rclpy
import threading

from rclpy.node import Node
from datetime import datetime
from enum import Enum

from sancho_interfaces.srv import SanchoPrompt, GetString
from sancho_interfaces.msg import ConversationTurn

from .log_manager import LogManager
from .memory_manager import MemoryManager
from .ais import create_sancho_ai, AIType, LLMTaskAI

class MODE(str, Enum):
    NORMAL = "normal"

    GET_NAME = "get_name"
    CONFIRM_NAME = "confirm_name"

    NO_ONE_KNOWN = "no_one_known"
    SOME_KNOWN = "some_known"
    ALL_KNOWN = "all_known"


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
        self.ai = create_sancho_ai(self.ai_type)
        self.memory_manager = MemoryManager()
        self.chats = {}

        self.conversation_log_pub = self.create_publisher(ConversationTurn, "conversation_log/add", 10)

        self.prompt_srv = self.create_service(SanchoPrompt, "sancho_hri/ai/prompt", self.prompt_service)
        self.get_memories_srv = self.create_service(GetString, "sancho_hri/ai/get_memories", self.get_memories_service)
        self.update_memory_srv = self.create_service(GetString, "sancho_hri/ai/update_memory", self.update_memory_service)

        LogManager.init(self)

        self.get_logger().info("SanchoAI Node initializated successfully")

    def prompt_service(self, request, response):
        args = {} if not request.args_json else json.loads(request.args_json)

        try:
            mode = MODE(request.mode)
        except ValueError:
            self.get_logger().error(f"Sancho prompt with unknown mode: {request.mode}")
            response.value_json = json.dumps({"error": "Unknown Mode"})
            return response

        if mode == MODE.NORMAL:
            self.get_logger().info("Normal Sancho Prompt")
            current_action = args.get("current_user_action", "desconocida")
            return self.normal_message(response, request.chat_id, request.text, args.get("user_id", ""), args.get("user_name", ""),current_action)
        
        elif mode in self.MODE_TASK:
            self.get_logger().info(f"{mode.name} Sancho Prompt")
            return self.task_message(response, request.text, args, self.MODE_TASK[mode])
        
        else:
            self.get_logger().error(f"Sancho prompt with mode that has no associated task: {mode}")
            response.value_json = json.dumps({"error": "Unsupported Mode"})
            return response

    def get_memories_service(self, request, response):
        args = json.loads(request.args)
        faceprint_id = args.get("faceprint_id", "")
        versions = args.get("versions", False)

        if not faceprint_id:
            response.text = json.dumps(self.memory_manager.get_all_latest_memories())
        elif versions:
            response.text = json.dumps(self.memory_manager.get_all_versions(faceprint_id))
        else:
            response.text = json.dumps(self.memory_manager.get_memory(faceprint_id))

        return response
    
    def update_memory_service(self, request, response):
        args = json.loads(request.args)
        faceprint_id = args.get("faceprint_id", "")
        memory_text = args.get("memory_text", "")

        new_memory = self.memory_manager.direct_update_memory(faceprint_id, memory_text)
        response.text = json.dumps(new_memory)

        return response

    def normal_message(self, response, chat_id, text, real_user_id, real_user_name, current_user_action):
        display_user_id = real_user_id or "Unknown"
        display_user_name = real_user_name or "Usuario"
        user_timestamp = datetime.now().timestamp()

        chat_history = self.chats.get(chat_id, [])
        user_memory = self.memory_manager.get_memory_text(real_user_id) # If no user_id, memory will be ""
        value, intent, arguments, provider, model = self.ai.on_message(text, chat_history, display_user_id, display_user_name, user_memory, current_user_action)
        assistant_timestamp = datetime.now().timestamp()

        response.value_json = json.dumps(value)
        response.method = self.ai_type
        response.intent = intent
        response.args_json = json.dumps(arguments)
        response.provider = provider
        response.model = model


        # Update memory (Could be handled inside on_message, only if unknown intent...)
        if real_user_id: # Only if we have a user_id, we wont store memory for unknown users
            chat_history_copy = list(chat_history) # bc of race conditions with appends bellow
            threading.Thread(
                target=self.memory_manager.update_memory, 
                args=(text, chat_history_copy, display_user_id, display_user_name), 
                daemon=True
            ).start()


        # Update chat history
        chat_history.append({"role": "user", "content": text, "id": display_user_id, "name": display_user_name})
        chat_history.append({"role": "assistant", "content": value["text"]}) # El llm no respeta (lo que pone abajo)
        # hacer que en el chat history tmb se guarde la emocion y lo que haga falta y en los unknown prompt formatear el chat history para eso
        # en cada prompt system se formatea como mejor convenga

        # Antes guardaba esto asi porque el LLM repetia mejor le hecho de poner response y emotion asi en JSON, si no fallaba mas
        # Lo comento de momento y si resulta que vuelve a fallar mas pues vuelvo a ese formato y ya veo como lo hago
        #chat_history.append({"role": "assistant", "content": json.dumps({"response": value["text"], "emotion": value["emotion"]})})
        self.chats[chat_id] = chat_history[-20:] # últimos 10 turnos (20 mensajes)

        # Add to logs
        self.conversation_log_pub.publish(ConversationTurn(
            chat_id=chat_id,

            user_timestamp=user_timestamp,
            user_id=real_user_id,
            user_name=real_user_name,
            user_text=text,
            user_intent=intent,
            user_arguments_json=json.dumps(arguments),

            assistant_timestamp=assistant_timestamp,
            assistant_text=value["text"],
            assistant_value_json=json.dumps(value),
            assistant_provider=provider,
            assistant_model=model
        ))

        return response

    def task_message(self, response, text, args, task_method):
        value, provider, model = task_method(text, args)
        
        response.value_json = json.dumps(value)
        response.provider = provider
        response.model = model

        return response

def main(args=None):
    rclpy.init(args=args)

    node = SanchoAINode(AIType.LLM_CLASSIFIER_GENERATOR)

    rclpy.spin(node)
    rclpy.shutdown()