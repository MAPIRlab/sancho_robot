from .coqui_multi_tts import CoquiMultiTTS
from ..models import TTS_SPEAKERS


class XTTS(CoquiMultiTTS):

    def __init__(self):
        super().__init__(
            model="tts_models/multilingual/multi-dataset/xtts_v2",
            language="es"    
        )

    def get_speakers(self) -> list[str]:
        return list(TTS_SPEAKERS.XTTS)