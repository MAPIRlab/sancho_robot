from rumi_msgs.srv import GetString

from .service_engine import ServiceEngine


class SessionEngine(ServiceEngine):
    def __init__(self, node):
        super().__init__(node)

        self.get_sessions_cli = self.create_client(GetString, 'rumi/sessions/get')
        self.get_sessions_summary_cli = self.create_client(GetString, 'rumi/sessions/get_summary')

        self.node.get_logger().info("Session Engine initializated successfully")

    def get_sessions_request(self, args_msg=""):
        req = GetString.Request()
        req.args = args_msg

        result = self.call_service(self.get_sessions_cli, req)

        return result.text
    
    def get_sessions_summary_request(self):
        req = GetString.Request()

        result = self.call_service(self.get_sessions_summary_cli, req)

        return result.text  