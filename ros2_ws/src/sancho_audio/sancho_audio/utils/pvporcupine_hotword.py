import os
import struct
import pvporcupine

import numpy as np

from scipy.signal import resample_poly
from dotenv import load_dotenv
from .model_hotword import ModelHotword


class PVPorcupineHotword(ModelHotword):
    
    def __init__(self):
        load_dotenv()

        device = os.environ.get("DEVICE")
        access_key = os.environ.get(f"PICOVOICE_API_KEY_{device}")
        wake_word_path = os.path.join(os.path.dirname(__file__), f"models/sancho_linux_{device.lower()}.ppn")
        model_path = os.path.join(os.path.dirname(__file__), "models/porcupine_params_es.pv")

        self.porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[wake_word_path],
            model_path=model_path
        )

        self.buffer = np.array([], dtype=np.int16)

    def detect(self, audio_chunk: list[int], sample_rate: int) -> bool:
        audio_np = np.array(audio_chunk, dtype=np.int16)

        if sample_rate != self.porcupine.sample_rate:
            audio_np = audio_np.astype(np.float32) / 32768.0
            audio_np = resample_poly(audio_np, self.porcupine.sample_rate, sample_rate)
            audio_np = np.round(audio_np * 32768.0).astype(np.int16)

        self.buffer = np.concatenate((self.buffer, audio_np))

        while len(self.buffer) >= self.porcupine.frame_length:
            frame = self.buffer[:self.porcupine.frame_length]
            self.buffer = self.buffer[self.porcupine.frame_length:]

            pcm = struct.pack("h" * self.porcupine.frame_length, *frame)
            pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)

            result = self.porcupine.process(pcm)
            if result >= 0:
                return True

        return False
