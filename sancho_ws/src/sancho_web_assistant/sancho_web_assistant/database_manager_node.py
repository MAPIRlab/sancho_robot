import os
import json
import rclpy
from rclpy.node import Node

from hri_msgs.msg import Log
from hri_msgs.srv import GetString

from .database.system_database import SystemDatabase


class DatabaseManagerNode(Node):
    def __init__(self):
        super().__init__('database_manager_node')

        self.get_logs_service_srv = self.create_service(GetString, 'logs/get', self.get_logs_service)
        self.log_sub = self.create_subscription(Log, 'logs/add', self.log_callback, 10)

        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database/system.db"))
        self.db = SystemDatabase(self.db_path)

        self.get_logger().info("Database Manager Node initializated succesfully")

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


def main(args=None):
    rclpy.init(args=args)

    node = DatabaseManagerNode()
    rclpy.spin(node)

    rclpy.shutdown()
