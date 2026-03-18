from .doa_method import DOAMethod

from .gcc_phat_doa import GCCPHATDOA
from .ncc_doa import NCCDOA

from enum import Enum


class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class DOA_METHODS(SmartStrEnum):
    NCC = "ncc"
    GCC_PHAT = "gccphat"