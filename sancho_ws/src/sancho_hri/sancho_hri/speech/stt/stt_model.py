import gc
import torch

from abc import ABC, abstractmethod


class STTModel(ABC):

    @abstractmethod
    def transcribe(self, audio: list[int], sample_rate: int) -> str:
        pass

    def unload(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()