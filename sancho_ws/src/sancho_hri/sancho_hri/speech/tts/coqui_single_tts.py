import torch
import numpy as np
from TTS.api import TTS

from .coqui_tts import CoquiTTS


class CoquiSingleTTS(CoquiTTS):

    def __init__(self, model):       
        self.model = TTS(model, progress_bar=False, gpu=torch.cuda.is_available())

    def synthesize(self, text: str, speaker: str) -> tuple[list[int], str]:
        audio = self.model.tts(text, speaker_wav=None)
        audio = np.clip(audio, -1.0, 1.0)
        audio = (audio * 32767).astype(np.int16)

        max_val = np.max(np.abs(audio))
        if max_val > 0:
            scale = 32767 / max_val
            audio = (audio.astype(np.float32) * scale).clip(-32767, 32767).astype(np.int16)

        return audio.tolist(), speaker

    def get_sample_rate(self) -> int:
        return self.model.synthesizer.output_sample_rate

    def unload(self):
        del self.model
        super().unload()