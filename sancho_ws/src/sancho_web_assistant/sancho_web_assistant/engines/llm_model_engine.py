from llm_msgs.msg import ProviderModel, LoadModel as LoadModelMsg
from llm_msgs.srv import GetModels, LoadModel, UnloadModel, GetActiveModels, SetActiveModel

from .service_engine import ServiceEngine


class LLMModelEngine(ServiceEngine):
    def __init__(self, node):
        super().__init__(node)

        self.get_models_cli = self.create_client(GetModels, 'llm_tools/get_all_models')
        self.get_available_cli = self.create_client(GetModels, 'llm_tools/get_available_models')
        self.get_active_cli = self.create_client(GetActiveModels, 'llm_tools/get_active_models')
        self.load_model_cli = self.create_client(LoadModel, 'llm_tools/load_model')
        self.unload_model_cli = self.create_client(UnloadModel, 'llm_tools/unload_model')
        self.set_active_cli = self.create_client(SetActiveModel, 'llm_tools/set_active_llm')

        self.node.get_logger().info("LLM Engine initialized successfully")

    def get_all_models_request(self, providers=[]):
        req = GetModels.Request()
        req.providers = providers

        result = self.call_service(self.get_models_cli, req)

        return [[i.provider, i.needs_api_key, i.executed_locally, i.models] for i in result.llm_models], result.providers

    def get_available_models_request(self, providers=[]):
        req = GetModels.Request()
        req.providers = providers

        result = self.call_service(self.get_available_cli, req)

        return [[i.provider, i.needs_api_key, i.executed_locally, i.models] for i in result.llm_models], result.providers

    def get_active_model_request(self):
        req = GetActiveModels.Request()

        result = self.call_service(self.get_active_cli, req)

        return result.llm_provider, result.llm_model

    def load_model_request(self, items_list):
        req = LoadModel.Request()

        req.items = []
        for [provider, models, api_key] in items_list:
            req.items.append(LoadModelMsg(provider=provider, models=models, api_key=api_key))

        result = self.call_service(self.load_model_cli, req)

        return [[i.provider, i.models, i.message, i.success] for i in result.results]

    def unload_model_request(self, items_list):
        req = UnloadModel.Request()

        req.items = []
        for [provider, models] in items_list:
            req.items.append(ProviderModel(provider=provider, models=models))

        result = self.call_service(self.unload_model_cli, req)

        return [[i.provider, i.models, i.message, i.success] for i in result.results]

    def set_active_model_request(self, provider, model):
        req = SetActiveModel.Request()
        req.provider = provider
        req.model = model

        result = self.call_service(self.set_active_cli, req)

        return result.message, result.success
