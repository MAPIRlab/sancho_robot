from rclpy.node import Node

class LogManager:
    _node: Node | None = None

    @classmethod
    def init(cls, node: Node):
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
