from enum import Enum

from .base_encoder import BaseEncoder
from .factory import load_encoder

class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class DBMode(SmartStrEnum):
    SAVE = "save",
    NO_SAVE = "no_save"

class EncoderType(SmartStrEnum):
    FACENET = "facenet"
    ARCFACE = "arcface"
    DINOV2 = "dinov2"
    OPENFACE = "openface"
    SFACE = "sface"
    VGGFACE = "vggface"