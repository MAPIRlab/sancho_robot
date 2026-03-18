from abc import ABC, abstractmethod


class ChunkAttachCriterion(ABC):

    @abstractmethod
    def should_attach_chunk(self, chunk, sample_rate):
        pass