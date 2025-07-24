from speech_msgs.msg import LoadModel as LoadModelMsg
from speech_msgs.srv import TTSGetActiveModel, TTSGetModels, TTSSetActiveModel, LoadModel, UnloadModel

from .service_engine import ServiceEngine


class TTSModelEngine(ServiceEngine):
    def __init__(self, node):
        super().__init__(node)

        self.get_models_cli = self.create_client(TTSGetModels, 'speech_tools/tts/get_all_models')
        self.get_available_cli = self.create_client(TTSGetModels, 'speech_tools/tts/get_available_models')
        self.get_active_cli = self.create_client(TTSGetActiveModel, 'speech_tools/tts/get_active_model')
        self.load_model_cli = self.create_client(LoadModel, 'speech_tools/tts/load_model')
        self.unload_model_cli = self.create_client(UnloadModel, 'speech_tools/tts/unload_model')
        self.set_active_cli = self.create_client(TTSSetActiveModel, 'speech_tools/tts/set_active_model')

        self.node.get_logger().info("TTS Engine initializated successfully")

    def get_all_models_request(self, models=[]):
        req = TTSGetModels.Request()
        req.models = models
        
        result = self.call_service(self.get_models_cli, req)

        return [[i.model, i.needs_api_key, i.speakers] for i in result.speakers], result.models

    def get_available_models_request(self, models=[]):
        req = TTSGetModels.Request()
        req.models = models
        
        result = self.call_service(self.get_available_cli, req)

        return [[i.model, i.needs_api_key, i.speakers] for i in result.speakers], result.models

    def get_active_model_request(self):
        req = TTSGetActiveModel.Request()

        result = self.call_service(self.get_active_cli, req)

        return result.model, result.speaker

    def load_model_request(self, items_list):
        req = LoadModel.Request()

        req.items = []
        for [model, api_key] in items_list:
            req.items.append(LoadModelMsg(model=model, api_key=api_key))
        
        result = self.call_service(self.load_model_cli, req)
        
        return [[i.model, i.message, i.success] for i in result.results]

    def unload_model_request(self, models):
        req = UnloadModel.Request()
        req.models = models
        
        result = self.call_service(self.unload_model_cli, req)

        return [[i.model, i.message, i.success] for i in result.results]

    def set_active_model_request(self, model, speaker):
        req = TTSSetActiveModel.Request()
        req.model = model
        req.speaker = speaker
        
        result = self.call_service(self.set_active_cli, req)

        return result.message, result.success