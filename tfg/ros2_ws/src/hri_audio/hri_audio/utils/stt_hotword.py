import re
import unidecode
import numpy as np
from .model_hotword import ModelHotword


class STTHotword(ModelHotword):
    
    def __init__(self, stt_request_fn, name: str = "Sancho", max_seconds: float = 2.0):
        self.name = name
        self.stt_request = stt_request_fn
        self.max_seconds = max_seconds

        self.buffer = np.array([], dtype=np.int16)

    def detect(self, audio_chunk: list[int], sample_rate: int) -> bool:
        audio_np = np.array(audio_chunk, dtype=np.int16)

        self.buffer = np.concatenate((self.buffer, audio_np))

        if len(self.buffer) >= self.max_seconds * sample_rate:
            transcript = self._transcribe(self.buffer, sample_rate)
            self.buffer = []

            return self._check_hotword(transcript)

        return False

    def _transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        try:
            audio_list = list(map(int, audio))
            result = self.stt_request(audio_list, sample_rate)
            return result if result else ""
        except Exception as e:
            return ""

    def _check_hotword(self, transcript: str) -> bool:
        if not transcript:
            return False

        processed = transcript.strip().lower()
        processed = unidecode.unidecode(processed)
        processed = re.sub(r'[^a-z\s]', '', processed)

        if self.name.lower() in processed:
            return True

        return False
