import json
from ..engines import LLMModelEngine
from .api_responses import HTTPException, JSONResponse, APIResponse
from sancho_web_assistant.database.system_database import CONSTANTS


class LLMModelAPI:

    def __init__(self, node):
        self.engine = LLMModelEngine(node)

    def get_all_llm_providers(self, providers: list[str] = []) -> APIResponse:
        providers_response = []

        [all_providers, _] = self.engine.get_all_models_request(providers)
        [available_providers, _] = self.engine.get_available_models_request(providers)
        [active_provider, active_model] = self.engine.get_active_model_request()

        available_map = {
            provider: set(models) for [provider, _, _, models] in available_providers
        }

        for [provider, needs_api_key, executed_locally, models] in all_providers:
            models_data = []
            for model in models:
                loaded = model in available_map.get(provider, set())
                active = provider == active_provider and model == active_model

                item = self._build_model_dict(model, loaded, active)
                models_data.append(item)

            item = self._build_provider_dict(provider, needs_api_key, executed_locally, models_data)
            providers_response.append(item)

        return JSONResponse(content=providers_response)

    def get_llm_provider(self, provider: str) -> APIResponse:
        [all_providers, _] = self.engine.get_all_models_request([provider])
        if not all_providers:
            raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found.")

        [available_providers, _] = self.engine.get_available_models_request([provider])
        [active_provider, active_model] = self.engine.get_active_model_request()

        models_all = next((p for p in all_providers if p[0] == provider), None)
        models_available = next((p for p in available_providers if p[0] == provider), None)

        if not models_all:
            raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found.")

        [_, needs_api_key, executed_locally, models] = models_all
        available_models = models_available[3] if models_available else []

        models_data = []
        for model in models:
            loaded = model in available_models
            active = provider == active_provider and model == active_model

            item = self._build_model_dict(model, loaded, active)
            models_data.append(item)

        item = self._build_provider_dict(provider, needs_api_key, executed_locally, models_data)

        return JSONResponse(content=item)

    def load_llm_model(self, provider: str, model: str, api_key: str) -> APIResponse:
        results = self.engine.load_model_request([[provider, [model], api_key]])
        [_, _, message, success] = results[0]

        if success:
            log_message = f"Se ha cargado correctamente el LLM {model} del provider {provider} desde la web"
            metadata_json = json.dumps({ "provider": provider, "model": model })
            self.engine.create_log(CONSTANTS.ACTION.LOAD_LLM_MODEL, "llm_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def unload_llm_model(self, provider: str, model: str) -> APIResponse:
        results = self.engine.unload_model_request([[provider, [model]]])
        [_, _, message, success] = results[0]

        if success:
            log_message = f"Se ha liberado correctamente el LLM {model} del provider {provider} desde la web"
            metadata_json = json.dumps({ "provider": provider, "model": model })
            self.engine.create_log(CONSTANTS.ACTION.UNLOAD_LLM_MODEL, "llm_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def set_active_llm_model(self, provider: str, model: str) -> APIResponse:
        [message, success] = self.engine.set_active_model_request(provider, model)

        if success:
            log_message = f"Se ha activado el LLM {model} del provider {provider} desde la web"
            metadata_json = json.dumps({ "provider": provider, "model": model })
            self.engine.create_log(CONSTANTS.ACTION.LOAD_LLM_MODEL, "llm_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def _build_provider_dict(self, provider: str, needs_api_key: bool, executed_locally: bool, models: list[dict]) -> dict:
        return {
            "provider": provider,
            "needs_api_key": needs_api_key,
            "executed_locally": executed_locally,
            "models": models
        }

    def _build_model_dict(self, model: str, loaded: bool, active: bool) -> dict:
        return {
            "model": model,
            "loaded": loaded,
            "active": active
        }
