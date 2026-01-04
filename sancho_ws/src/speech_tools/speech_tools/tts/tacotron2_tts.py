from .coqui_single_tts import CoquiSingleTTS
from ..models import TTS_SPEAKERS


class Tacotron2TTS(CoquiSingleTTS):

    def __init__(self):
        super().__init__(
            model="tts_models/es/mai/tacotron2-DDC"
        )

    def get_speakers(self) -> list[str]:
        return list(TTS_SPEAKERS.TACOTRON2)