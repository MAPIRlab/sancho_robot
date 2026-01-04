from .coqui_single_tts import CoquiSingleTTS
from ..models import TTS_SPEAKERS


class CSS10TTS(CoquiSingleTTS):

    def __init__(self):
        super().__init__(
            model="tts_models/es/css10/vits"
        )

    def get_speakers(self) -> list[str]:
        return list(TTS_SPEAKERS.CSS10)