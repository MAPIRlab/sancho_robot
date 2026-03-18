from sancho_interfaces.srv import GetString

from .service_engine import ServiceEngine


class MemoryEngine(ServiceEngine):
    def __init__(self, node):
        super().__init__(node)

        self.get_memories_cli = self.create_client(GetString, 'sancho_ai/get_memories')
        self.update_memory_cli = self.create_client(GetString, 'sancho_ai/update_memory')

        self.node.get_logger().info("Memory Engine initializated successfully")

    def get_memories_request(self, args_msg=""):
        req = GetString.Request()
        req.args = args_msg

        result = self.call_service(self.get_memories_cli, req)

        return result.text

    def update_memory_request(self, args_msg=""):
        req = GetString.Request()
        req.args = args_msg

        result = self.call_service(self.update_memory_cli, req)

        return result.text
