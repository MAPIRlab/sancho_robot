from abc import ABC, abstractmethod


class DOAMethod(ABC):

    @abstractmethod
    def calc_doa(left_mic, right_mic, sample_rate):
        pass