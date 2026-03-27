import numpy as np


def gcc_phat(
    signal_1: np.ndarray,
    signal_2: np.ndarray,
    fs: int,
    max_tau: float = None,
    interp: int = 16,
):
    """Estimate time-delay using GCC-PHAT"""
    n = signal_1.shape[0] + signal_2.shape[0]
    # FFT of both signals
    SIG1 = np.fft.rfft(signal_1, n=n)
    SIG2 = np.fft.rfft(signal_2, n=n)
    # Cross-spectral density
    R = SIG1 * np.conj(SIG2)
    # PHAT weighting
    R /= np.abs(R) + 1e-8
    # Inverse FFT to get cross-correlation
    cc = np.fft.irfft(R, n=(interp * n))

    max_shift = int(interp * n / 2)
    if max_tau:
        max_shift = np.minimum(int(interp * fs * max_tau), max_shift)
    cc = np.concatenate((cc[-max_shift:], cc[: max_shift + 1]))
    # Find max index
    shift = np.argmax(np.abs(cc)) - max_shift
    tau = shift / float(interp * fs)
    return tau, cc
