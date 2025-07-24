import json
import rclpy

from queue import Queue

from .http_server import HTTPServer
from .websocket_thread_mixer import WebSocketThreadMixer
from .websocket_server import WebSocketServer
from .stoppable_node import StoppableNode
from .dynamic_subscribable_node import DynamicSubscribableNode
from .protocol import MessageType, JSONMessage, Message, TopicMessage, parse_message
from .chunk_protocol import ChunkMessageType, parse_chunk_message
from .chunk_manager import ChunkManager
from .r2w_bridge import R2WBridge

from ros2web_msgs.msg import R2WMessage


class ServerNode(DynamicSubscribableNode):

    def __init__(self):
        super().__init__("server")

        self.ros_queue = Queue()
        self.broadcast_topics = {}

        self.ros_sub = self.create_subscription(R2WMessage, "ros2web/ros", self.server_callback, 10)
        self.web_pub = self.create_publisher(R2WMessage, "ros2web/web", 10)

        self.r2w_bridge = R2WBridge()
        self.get_logger().info("Server Node initializated successfully")

    def server_callback(self, msg):
        self.ros_queue.put([msg.key, msg.value])

    def generic_callback(self, topic, name, value):
        self.broadcast_topics[topic] = [name, value]


class Server(StoppableNode):

    def __init__(self):
        super().__init__()

        self.node = ServerNode()
        self.ws = WebSocketServer(self.on_message_chunked, self.on_user_connect, self.on_user_disconnect)
        self.http_server = HTTPServer(port=8173, open_on_start=self.node.declare_parameter("open_on_start", True).get_parameter_value().bool_value)

        self.chunk_manager = ChunkManager()

    def spin(self):
        if self.node.ros_queue.qsize() > 0:
            [key, value] = self.node.ros_queue.get()

            message = Message(value)

            if key:
                self.send_chunked(key, message)
            else:
                self.broadcast_chunked(message)

        for topic in self.node.broadcast_topics:
            data = self.node.broadcast_topics[topic]
            if data is not None:
                [name, value] = data
                value = self.node.r2w_bridge.any_to_r2w(value)

                message = TopicMessage(topic, name, value)

                self.node.broadcast_topics[topic] = None
                self.broadcast_chunked(message)

    def on_message(self, key, msg):
        type, data = parse_message(msg)
        self.node.get_logger().info(f"Message received from ({key}).")

        if type == MessageType.MESSAGE:
            self.node.web_pub.publish(R2WMessage(key=key, value=data)) # Data is already JSON

    def on_message_chunked(self, key, msg):
        type, id, chunk_index, final, data = parse_chunk_message(msg) 
        self.node.get_logger().info(f"Chunk received from ({key}): Index={chunk_index} Final={final}")

        if type == ChunkMessageType.CHUNK:
            full_data = self.chunk_manager.chunk_to_msg(id, chunk_index, final, data)
            if full_data:
                self.on_message(key, full_data)

    def send_chunked(self, key, msg: JSONMessage):
        client = self.ws.get_client(key)
        self.node.get_logger().info(f"Sending message to ({key}).")
        for chunk in self.chunk_manager.msg_to_chunks(msg.to_json()):
            self.node.get_logger().info(f"Sending chunk to ({key}): Index={chunk.chunk_index} Final={chunk.final}")
            self.ws.send_message(client, chunk.to_json())

    def broadcast_chunked(self,  msg: JSONMessage):
        for chunk in self.chunk_manager.msg_to_chunks(msg.to_json()):
            self.ws.broadcast_message(chunk.to_json())

    def on_user_connect(self, key):
        self.node.get_logger().info(f"Client connected ({key}) (Connections: {self.ws.get_connection_count()})")

    def on_user_disconnect(self, key):
        self.node.get_logger().info(f"Client disconnected ({key}) (Connections: {self.ws.get_connection_count()})")


def main(args=None):
    rclpy.init(args=args)

    server = Server()
    websocket_thread_mixer = WebSocketThreadMixer(server.ws, server, server.http_server)
    websocket_thread_mixer.run()
