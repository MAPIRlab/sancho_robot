from rclpy.node import Node
from typing import Optional

class LogManager:
    _node: Optional[Node] = None

    @classmethod
    def set_node(cls, node: Node):
        cls._node = node

    @classmethod
    def info(cls, msg: str):
        if cls._node:
            cls._node.get_logger().info(msg)

    @classmethod
    def warn(cls, msg: str):
        if cls._node:
            cls._node.get_logger().warn(msg)

    @classmethod
    def error(cls, msg: str):
        if cls._node:
            cls._node.get_logger().error(msg)

    @classmethod
    def debug(cls, msg: str):
        if cls._node:
            cls._node.get_logger().debug(msg)
