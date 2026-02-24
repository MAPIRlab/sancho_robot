import torch
import numpy as np
from bark import generate_audio, preload_models, SAMPLE_RATE

from .tts_model import TTSModel
from ..models import TTS_SPEAKERS


class BarkTTS(TTSModel):

    def __init__(self):
        use_gpu = torch.cuda.is_available()
        preload_models(
            text_use_gpu=use_gpu, 
            fine_use_gpu=use_gpu, 
            codec_use_gpu=use_gpu, 
            coarse_use_gpu=use_gpu
        )

    def synthesize(self, text: str, speaker: str) -> tuple[list[int], str]:
        if not speaker:
            speaker = self.get_speakers()[0]

        audio = generate_audio(text, history_prompt=speaker)
        audio = np.clip(audio, -1.0, 1.0)
        audio = (audio * 32767).astype(np.int16)

        max_val = np.max(np.abs(audio))
        if max_val > 0:
            scale = 32767 / max_val
            audio = (audio.astype(np.float32) * scale).clip(-32767, 32767).astype(np.int16)

        return audio.tolist(), speaker

    def get_sample_rate(self) -> int:
        return SAMPLE_RATE
    
    def get_speakers(self) -> list[str]:
        return list(TTS_SPEAKERS.BARK)