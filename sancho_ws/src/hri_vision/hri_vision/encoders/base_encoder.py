from abc import ABC, abstractmethod


class BaseEncoder(ABC):

    @abstractmethod
    def encode_face(self, face):
        pass