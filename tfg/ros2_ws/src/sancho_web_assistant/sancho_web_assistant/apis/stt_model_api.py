import json
from ..engines import STTModelEngine
from .api_responses import HTTPException, JSONResponse, APIResponse
from sancho_web_assistant.database.system_database import CONSTANTS


class STTModelAPI:

    def __init__(self, node):
        self.engine = STTModelEngine(node)

    def get_all_stt_models(self, models: list[str] = []) -> APIResponse:
        models_response = []

        all_models_info = self.engine.get_all_models_request(models)
        loaded_models_info = self.engine.get_available_models_request(models)
        active_model = self.engine.get_active_model_request()

        loaded_models = [m[0] for m in loaded_models_info]

        for [model, needs_api_key] in all_models_info:
            loaded = model in loaded_models
            active = model == active_model

            item = self._build_model_dict(model, needs_api_key, loaded, active)
            models_response.append(item)

        return JSONResponse(content=models_response)

    def get_stt_model(self, model: str) -> APIResponse:
        all_models_info = self.engine.get_all_models_request([model])
        if not all_models_info:
            raise HTTPException(status_code=404, detail=f"Model '{model}' not found.")

        loaded_models_info = self.engine.get_available_models_request([model])
        active_model = self.engine.get_active_model_request()

        model_name, needs_api_key = all_models_info[0]
        loaded = model_name in [m[0] for m in loaded_models_info]
        active = model_name == active_model

        item = self._build_model_dict(model_name, needs_api_key, loaded, active)

        return JSONResponse(content=item)

    def load_stt_model(self, model: str, api_key: str) -> APIResponse:
        results = self.engine.load_model_request([[model, api_key]])
        [_, message, success] = results[0]

        if success:
            log_message = f"Se ha cargado correctamente el modelo STT {model} desde la web"
            metadata_json = json.dumps({ "model": model })
            self.engine.create_log(CONSTANTS.ACTION.LOAD_STT_MODEL, "stt_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def unload_stt_model(self, model: str) -> APIResponse:
        results = self.engine.unload_model_request([model])
        [_, message, success] = results[0]

        if success:
            log_message = f"Se ha liberado correctamente el modelo STT {model} desde la web"
            metadata_json = json.dumps({ "model": model })
            self.engine.create_log(CONSTANTS.ACTION.UNLOAD_STT_MODEL, "stt_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def set_active_stt_model(self, model: str) -> APIResponse:
        message, success = self.engine.set_active_model_request(model)

        if success:
            log_message = f"Se ha activado correctamente el modelo STT {model} desde la web"
            metadata_json = json.dumps({ "model": model })
            self.engine.create_log(CONSTANTS.ACTION.ACTIVE_STT_MODEL, "stt_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def _build_model_dict(self, model, needs_api_key, loaded, active):
        item = {
            "model": model,
            "needs_api_key": needs_api_key,
            "loaded": loaded,
            "active": active,
        }
        return item
