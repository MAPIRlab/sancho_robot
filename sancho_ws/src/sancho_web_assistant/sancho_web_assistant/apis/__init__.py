from .api_responses import APIResponse, HTTPException, JSONResponse
from .faceprint_api import FaceprintAPI
from .log_api import LogAPI
from .session_api import SessionAPI
from .tts_model_api import TTSModelAPI
from .stt_model_api import STTModelAPI
from .llm_model_api import LLMModelAPI

from enum import Enum


class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class API_LIST(SmartStrEnum):
    FACEPRINTS = "faceprints"
    LOGS = "logs"
    SESSIONS = "sessions"
    TTS_MODELS = "tts_models"
    STT_MODELS = "stt_models"
    LLM_MODELS = "llm_models"