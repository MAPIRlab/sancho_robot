import gc
import torch
import numpy as np
import soundfile as sf
import sounddevice as sd

from abc import ABC, abstractmethod


class TTSModel(ABC):

    @abstractmethod
    def synthesize(self, text: str, speaker: str) -> tuple[list[int], str]:
        pass
    
    @abstractmethod
    def get_sample_rate(self) -> int:
        pass
    
    @abstractmethod
    def get_speakers(self) -> list[str]:
        pass

    def unload(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    @staticmethod
    def save(filepath, audio, sample_rate):
        audio = np.array(audio, dtype=np.int16)
        
        sf.write(filepath, audio, samplerate=sample_rate, subtype="PCM_16")

    @staticmethod
    def play(audio, sample_rate, wait=True):
        audio = np.array(audio, dtype=np.int16)

        sd.play(audio, samplerate=sample_rate)
        if wait:
            sd.wait()