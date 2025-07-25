import ast
import rclpy
from rclpy.node import Node

import uvicorn

from .service.app import app
from .service.v1_faceprints import set_faceprint_api
from .service.v1_logs import set_log_api
from .service.v1_sessions import set_session_api
from .service.v1_tts_models import set_tts_model_api
from .service.v1_stt_models import set_stt_model_api
from .service.v1_llm_models import set_llm_model_api

from .apis import FaceprintAPI, LogAPI, SessionAPI, TTSModelAPI, STTModelAPI, LLMModelAPI, API_LIST


class APIRESTNode(Node):

    AVAILABLE_APIS = {
        API_LIST.FACEPRINTS: (FaceprintAPI, set_faceprint_api),
        API_LIST.LOGS: (LogAPI, set_log_api),
        API_LIST.SESSIONS: (SessionAPI, set_session_api),
        API_LIST.TTS_MODELS: (TTSModelAPI, set_tts_model_api),
        API_LIST.STT_MODELS: (STTModelAPI, set_stt_model_api),
        API_LIST.LLM_MODELS: (LLMModelAPI, set_llm_model_api)
    }

    def __init__(self):
        super().__init__("api_rest_node")

        apis = self.parse_string_list(self.declare_parameter("apis", "[]").get_parameter_value().string_value)
        self.configure_apis(apis)

        self.get_logger().info("API REST Node initializated successfully.")

    def spin(self):
        uvicorn.run(app, host="0.0.0.0", port=7654)

    def configure_apis(self, selected):
        if not selected:
            selected = list(self.AVAILABLE_APIS.keys())

        for api_name in selected:
            if api_name not in self.AVAILABLE_APIS:
                self.get_logger().error(f"API '{api_name}' not found.")
            else:
                api_class, setter_fn = self.AVAILABLE_APIS[api_name]
                api_instance = api_class(node=self)
                setter_fn(api_instance)

    def parse_string_list(self, raw_string) -> list[str]:
        try:
            return ast.literal_eval(raw_string)
        except Exception:
            return []
        

def main(args=None):
    rclpy.init(args=args)

    api_rest_node = APIRESTNode()

    api_rest_node.spin()    
    rclpy.shutdown()
