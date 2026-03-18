import rclpy
from rclpy.node import Node
from rclpy.client import Client

from abc import ABC

from sancho_interfaces.msg import Log

from sancho_web_bridge.assistant.database.system_database import CONSTANTS


class ServiceEngine(ABC):
    
    def __init__(self, node: Node):
        self.node = node
        self.clients = {} 

        self.publisher_log = self.node.create_publisher(Log, 'logs/add', 10)

    def create_log(self, action, target, message="", metadata_json="", level=CONSTANTS.LEVEL.INFO):
        self.publisher_log.publish(Log(
            level=level,
            origin=CONSTANTS.ORIGIN.WEB,
            actor="An user",
            action=action,
            target=target,
            message=message,
            metadata_json=metadata_json
        ))

    def create_client(self, srv_type, srv_name):
        if srv_name in self.clients:
            return self.clients[srv_name]

        # Simply create and register the client. DO NOT block the thread here.
        client = self.node.create_client(srv_type, srv_name)
        self.clients[srv_name] = client
        
        return client

    def call_service(self, client: Client, request, timeout_sec=2.0):
        # 1. Check if the service is alive before committing to the call.
        # This gives offline services a brief window to respond without hanging the web request forever.
        if not client.wait_for_service(timeout_sec=timeout_sec):
            self.node.get_logger().error(f"Service {client.srv_name} is offline or unreachable.")
            raise TimeoutError(f"El servicio {client.srv_name} no está disponible.")

        # 2. Proceed with the call if the service is ready
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future)
        result = future.result()

        return result