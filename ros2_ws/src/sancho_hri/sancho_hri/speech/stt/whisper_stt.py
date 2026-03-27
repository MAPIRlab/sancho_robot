import os
import torch
import torchaudio
import tempfile

from faster_whisper import WhisperModel

from .stt_model import STTModel


class WhisperSTT(STTModel):
    def __init__(self, model_size: str = "large-v3", device: str = "cuda", compute_type: str = "float16"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: list[int], sample_rate: int) -> str:
        try:
            audio_tensor = torch.tensor(audio, dtype=torch.float32) / 32768.0
            audio_tensor = audio_tensor.unsqueeze(0)  # (1, num_samples)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
                tmp_path = tmpfile.name
                torchaudio.save(tmp_path, audio_tensor, sample_rate)

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
