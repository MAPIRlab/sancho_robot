import os
import urllib.request
import numpy as np
from scipy.signal import resample_poly
from openwakeword.model import Model

from .model_hotword import ModelHotword


class OpenWakeWordHotword(ModelHotword):
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        self.model_path = os.path.join(base_dir, "models/sancho_wakeword.onnx")

        cache_dir = os.path.expanduser("~/.cache/openwakeword/models")
        self.melspec = os.path.join(cache_dir, "melspectrogram.onnx")
        self.embed = os.path.join(cache_dir, "embedding_model.onnx")
        if not os.path.isfile(self.melspec):
            os.makedirs(cache_dir, exist_ok=True)
            urllib.request.urlretrieve(
                "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx",
                self.melspec,
            )
        if not os.path.isfile(self.embed):
            os.makedirs(cache_dir, exist_ok=True)
            urllib.request.urlretrieve(
                "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx",
                self.embed,
            )

        self.target_rate = 16000
        self.frame_ms = 80
        self.samples_per_frame = self.target_rate * self.frame_ms // 1000
        self.threshold = 0.100
        self.frames_needed = 1

        self.model = Model(
            wakeword_models=[self.model_path],
            inference_framework="onnx",
            vad_threshold=0.0,
            enable_speex_noise_suppression=False,
            melspec_model_path=self.melspec,
            embedding_model_path=self.embed,
        )

        self.buffer = np.array([], dtype=np.int16)
        self.consec_hits = 0

    def detect(self, audio_chunk: list[int], sample_rate: int) -> bool:
        if not audio_chunk:
            return False

        x = np.asarray(audio_chunk, dtype=np.int16)
        if sample_rate != self.target_rate:
            x_f32 = x.astype(np.float32) / 32768.0
            x = np.round(resample_poly(x_f32, self.target_rate, sample_rate) * 32767.0).astype(np.int16)

        self.buffer = np.concatenate((self.buffer, x))
        fired = False

        while self.buffer.size >= self.samples_per_frame:
            frame = self.buffer[: self.samples_per_frame]
            self.buffer = self.buffer[self.samples_per_frame:]

            score = next(iter(self.model.predict(frame).values()))
            print(f"Hotword score: {score:.3f}")  # Debugging line to see the score

            if score >= self.threshold:
                self.consec_hits += 1
                if self.consec_hits >= self.frames_needed:
                    self.consec_hits = 0
                    self.buffer = np.array([], dtype=np.int16) # Limpiar buffer para evitar re-disparo
                    self.model.reset() # Limpia el estado interno del modelo para evitar re-disparos
                
                    fired = True
                    break
            else:
                self.consec_hits = 0

        return fired
