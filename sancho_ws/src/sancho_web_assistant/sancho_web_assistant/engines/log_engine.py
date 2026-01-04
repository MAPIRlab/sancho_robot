from hri_msgs.srv import GetString

from .service_engine import ServiceEngine


class LogEngine(ServiceEngine):
    def __init__(self, node):
        super().__init__(node)

        self.get_logs_cli = self.create_client(GetString, 'logs/get')

        self.node.get_logger().info("Log Engine initializated successfully")

    def get_logs_request(self, args_msg=""):
        req = GetString.Request()
        req.args = args_msg

        result = self.call_service(self.get_logs_cli, req)

        return result.text