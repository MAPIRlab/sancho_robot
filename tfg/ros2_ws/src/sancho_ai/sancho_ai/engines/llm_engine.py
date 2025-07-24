from .service_engine import ServiceEngine

from dotenv import load_dotenv

from llm_msgs.srv import Prompt


class LLMEngine(ServiceEngine):
    def __init__(self, node):
        super().__init__(node)

        load_dotenv()

        self.prompt_cli = self.create_client(Prompt, "llm_tools/prompt")

        self.node.get_logger().info("Prompt Engine initializated succesfully")


    def prompt_request(self, provider="", model="", prompt_system="", messages_json="", user_input="", parameters_json=""):
        req = Prompt.Request()
        req.provider = provider
        req.model = model
        req.prompt_system = prompt_system
        req.messages_json = messages_json
        req.user_input = user_input
        req.parameters_json = parameters_json

        result = self.call_service(self.prompt_cli, req)

        return result.response, result.provider_used, result.model_used, result.message, result.success
