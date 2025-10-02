import os
import json
import rclpy
from rclpy.node import Node

from hri_msgs.msg import Log
from sancho_msgs.msg import ConversationTurn
from hri_msgs.srv import GetString

from .database.system_database import SystemDatabase


class DatabaseManagerNode(Node):
    def __init__(self):
        super().__init__('database_manager_node')

        self.log_sub = self.create_subscription(Log, 'logs/add', self.log_callback, 10)
        self.conversation_log_sub = self.create_subscription(ConversationTurn, 'conversation_log/add', self.conversation_log_callback, 10)
        
        self.get_logs_srv = self.create_service(GetString, 'logs/get', self.get_logs_service)
        self.get_conversation_logs_srv = self.create_service(GetString, 'conversation_logs/get', self.get_conversation_logs_service)

        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database/system.db"))
        self.db = SystemDatabase(self.db_path)
        
        self.chat_conversation_map = {}

        self.get_logger().info("Database Manager Node initializated succesfully")

    # Subcription handlers
    def log_callback(self, msg):
        try:
            self.db.create_log(
                level=msg.level,
                origin=msg.origin,
                action=msg.action,
                actor=msg.actor if msg.actor else None,
                target=msg.target if msg.target else None,
                message=msg.message if msg.message else None,
                metadata_json=msg.metadata_json
            )

            self.get_logger().info(f"📝 Log recibido y almacenado: {msg.action} ({msg.actor} → {msg.target})")
        except Exception as e:
            self.get_logger().error(f"❌ Error procesando log: {e}")

    def conversation_log_callback(self, msg):
        if msg.chat_id not in self.chat_conversation_map:
            self.chat_conversation_map[msg.chat_id] = self.db.create_conversation(msg.user_timestamp)
        
        try:
            self.db.append_turn(
                conversation_id=self.chat_conversation_map[msg.chat_id],

                user_timestamp=msg.user_timestamp,
                user_id=msg.user_id,
                user_name=msg.user_name,
                user_text=msg.user_text,
                user_intent=msg.user_intent,
                user_arguments_json=msg.user_arguments_json,

                assistant_timestamp=msg.assistant_timestamp,
                assistant_text=msg.assistant_text,
                assistant_value_json=msg.assistant_value_json,
                assistant_provider=msg.assistant_provider,
                assistant_model=msg.assistant_model
            )

            self.get_logger().info((f"📝 Log de conversación recibido y almacenado"))
        except Exception as e:
            self.get_logger().error(f"❌ Error procesando log de conversación: {e}")

    # Service handlers
    def get_logs_service(self, request, response):
        args = json.loads(request.args) if request.args else {}
        log_id = args.get("id")
        
        if log_id is not None:
            log_id = int(log_id)
            log = self.db.get_log_by_id(log_id)
            response.text = json.dumps(log)
        else:
            logs = self.db.get_all_logs()
            response.text = json.dumps(logs)

        return response

    def get_conversation_logs_service(self, request, response):
        args = json.loads(request.args) if request.args else {}
        conversation_id = args.get("id")

        if conversation_id is not None:
            conversation_id = int(conversation_id)
            conversation = self.db.get_conversation_by_id(conversation_id)
            response.text = json.dumps(conversation)
        else:
            conversations = self.db.get_all_conversations()
            response.text = json.dumps(conversations)

        return response

def main(args=None):
    rclpy.init(args=args)

    node = DatabaseManagerNode()
    rclpy.spin(node)

    rclpy.shutdown()
