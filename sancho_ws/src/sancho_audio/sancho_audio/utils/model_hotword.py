from abc import ABC, abstractmethod


class ModelHotword(ABC):

    @abstractmethod
    def detect(self, audio_chunk: list[int], sample_rate: int) -> bool:
        pass