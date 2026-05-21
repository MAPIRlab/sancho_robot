import os
import torch
import numpy as np
from scipy.io import wavfile
import tempfile

from faster_whisper import WhisperModel

from .stt_model import STTModel


class WhisperSTT(STTModel):
    #def __init__(self, model_size: str = "large-v3", device: str = "cuda", compute_type: str = "float16"):
    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: list[int], sample_rate: int) -> str:
        try:
            # Convert audio list to numpy array (int16 is standard for WAV)
            audio_np = np.array(audio, dtype=np.int16)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
                tmp_path = tmpfile.name
                wavfile.write(tmp_path, sample_rate, audio_np)

            segments, _ = self.model.transcribe(tmp_path, language="es")
            text = " ".join([segment.text for segment in segments])

            return text

        except Exception as e:
            print(f"[WhisperSTT] Error: {e}")
            return ""

        finally:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def unload(self):
        del self.model
        super().unload()
