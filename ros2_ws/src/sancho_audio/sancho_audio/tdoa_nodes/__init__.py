"""Utilities for estimating Time Difference of Arrival (TDOA)."""

from __future__ import annotations

from abc import ABC, abstractmethod
import numpy as np

from .tdoa_gcc import gcc_phat
from .tdoa_ncc import normalized_cross_correlation


class TDOAStrategy(ABC):
    """Base interface for TDOA estimation strategies."""

    @abstractmethod
    def compute_delay(self, left: np.ndarray, right: np.ndarray) -> float:
        """Return the delay between ``left`` and ``right`` signals in seconds."""


class GccStrategy(TDOAStrategy):
    """Compute delay using the GCC-PHAT algorithm."""

    def __init__(self, sample_rate: int, mic_distance: float) -> None:
        self.sample_rate = sample_rate
        self.mic_distance = mic_distance

    def compute_delay(self, left: np.ndarray, right: np.ndarray) -> float:
        tau, _ = gcc_phat(
            left, right, fs=self.sample_rate, max_tau=self.mic_distance / 343.0
        )
        return float(tau)


class NccStrategy(TDOAStrategy):
    """Compute delay using normalized cross correlation."""

    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate

    def compute_delay(self, left: np.ndarray, right: np.ndarray) -> float:
        disp, _ = normalized_cross_correlation(left, right)
        tau = disp / float(self.sample_rate)
        return float(tau)


#: Registry of available strategies keyed by method name
STRATEGIES: dict[str, type[TDOAStrategy]] = {
    "gcc": GccStrategy,
    "ncc": NccStrategy,
}
