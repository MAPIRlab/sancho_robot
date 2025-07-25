import rclpy
from rclpy.node import Node
from rclpy.client import Client

from rclpy.executors import SingleThreadedExecutor
from threading import Thread, Event

from abc import ABC


class ServiceEngine(ABC):
    
    def __init__(self, node: Node):
        self.node = node

    def create_client(self, srv_type, srv_name, wait=True):
        client = self.node.create_client(srv_type, srv_name)
        while wait and not client.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().info(f'{srv_name} service not available, waiting again...')

        return client

    def call_service(self, client: Client, request):
        if not client.service_is_ready():
            self.node.get_logger().warn(f"Service'{client.srv_name}' not available")
            return None
        
        done_event = Event()
        result_holder = {}

        def done_cb(fut):
            try:
                result_holder["value"] = fut.result()
            except Exception as e:
                self.node.get_logger().info(f"Error al recibir respuesta: {e}", level="error")
                result_holder["value"] = None
            finally:
                done_event.set()

        future = client.call_async(request)
        future.add_done_callback(done_cb)
        done_event.wait()

        return result_holder["value"]

    @staticmethod
    def create_client_node(name="service_engine_client"):
        node = rclpy.create_node(name)

        executor = SingleThreadedExecutor()
        executor.add_node(node)

        thread = Thread(target=executor.spin, daemon=True)
        thread.start()

        return node
