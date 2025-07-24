import os
import numpy as np
from piper import PiperVoice

from .tts_model import TTSModel
from ..models import TTS_SPEAKERS


class PiperTTS(TTSModel):

    def __init__(self):
        path_dave = os.path.join(os.path.dirname(__file__), "tts_models/es_ES-davefx-medium.onnx")
        path_shar = os.path.join(os.path.dirname(__file__), "tts_models/es_ES-sharvard-medium.onnx")

        self.models = {
            "davefx": PiperVoice.load(path_dave, config_path=f"{path_dave}.json"),
            "sharvard": PiperVoice.load(path_shar, config_path=f"{path_shar}.json"),
        } 

    def synthesize(self, text: str, speaker: str) -> tuple[list[int], str]:
        if not speaker:
            speaker = self.get_speakers()[0]

        stream = self.models[speaker].synthesize_stream_raw(text)
        audio_bytes = b"".join(stream)
        audio = np.frombuffer(audio_bytes, dtype=np.int16)

        max_val = np.max(np.abs(audio))
        if max_val > 0:
            scale = 32767 / max_val
            audio = (audio.astype(np.float32) * scale).clip(-32767, 32767).astype(np.int16)

        return audio.tolist(), speaker

    def get_sample_rate(self) -> int:
        return next(iter(self.models.values())).config.sample_rate
    
    def get_speakers(self) -> list[str]:
        return list(TTS_SPEAKERS.PIPER)

    def unload(self):
        del self.models
        super().unload()