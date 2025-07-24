import json
from ..engines import TTSModelEngine
from .api_responses import HTTPException, JSONResponse, APIResponse
from sancho_web_assistant.database.system_database import CONSTANTS


class TTSModelAPI:

    def __init__(self, node):
        self.engine = TTSModelEngine(node)

    def get_all_tts_models(self, models: list[str] = []) -> APIResponse:
        models_response = []

        [all_modelspeaker, _] = self.engine.get_all_models_request(models)
        [_, loaded_models] = self.engine.get_available_models_request(models)
        [active_model, active_speaker] = self.engine.get_active_model_request()

        for [model, needs_api_key, speakers] in all_modelspeaker:
            loaded = model in loaded_models
            active = model == active_model

            item = self._build_model_dict(model, needs_api_key, speakers, loaded, active, active_speaker)
            models_response.append(item)

        return JSONResponse(content=models_response)

    def get_tts_model(self, model: str) -> APIResponse:
        [all_modelspeaker, _] = self.engine.get_all_models_request([model])
        if not all_modelspeaker:
            raise HTTPException(status_code=404, detail=f"Model '{model}' not found.")

        [_, loaded_models] = self.engine.get_available_models_request([model])
        [active_model, active_speaker] = self.engine.get_active_model_request()

        model, needs_api_key, speakers = all_modelspeaker[0]
        loaded = model in loaded_models
        active = model == active_model

        item = self._build_model_dict(model, needs_api_key, speakers, loaded, active, active_speaker)

        return JSONResponse(content=item)

    def load_tts_model(self, model: str, api_key: str) -> APIResponse:
        results = self.engine.load_model_request([[model, api_key]])
        [_, message, success] = results[0]

        if success:
            log_message = f"Se ha cargado correctamente el modelo TTS {model} desde la web"
            metadata_json = json.dumps({ "model": model })
            self.engine.create_log(CONSTANTS.ACTION.LOAD_TTS_MODEL, "tts_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def unload_tts_model(self, model: str) -> APIResponse:
        results = self.engine.unload_model_request([model])
        [_, message, success] = results[0]

        if success:
            log_message = f"Se ha liberado correctamente el modelo TTS {model} desde la web"
            metadata_json = json.dumps({ "model": model })
            self.engine.create_log(CONSTANTS.ACTION.UNLOAD_TTS_MODEL, "tts_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })
    
    def set_active_tts_model(self, model: str, speaker: str) -> APIResponse:
        message, success = self.engine.set_active_model_request(model, speaker)

        if success:
            log_message = f"Se ha cargado correctamente el modelo TTS {model} con la voz {speaker} desde la web"
            metadata_json = json.dumps({ "model": model, "speaker": speaker })
            self.engine.create_log(CONSTANTS.ACTION.ACTIVE_TTS_MODEL, "tts_node", log_message, metadata_json)

        return JSONResponse(content={
            "message": message,
            "success": success
        })

    def _build_model_dict(self, model, needs_api_key, speakers, loaded, active, active_speaker):
        item = {
            "model": model,
            "speakers": speakers,
            "needs_api_key": needs_api_key,
            "loaded": loaded,
            "active": active,
        }
        if active:
            item["speaker"] = active_speaker
        return item
