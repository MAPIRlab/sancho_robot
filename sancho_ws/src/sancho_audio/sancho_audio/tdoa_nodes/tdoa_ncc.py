import numpy as np
from scipy.ndimage import gaussian_filter1d


def normalized_cross_correlation(
    first_signal: np.ndarray, second_signal: np.ndarray
) -> float:
    """Calculates the Normalized Cross-Correlation (NCC) and finds the best delay."""
    # Smooth signals slightly to reduce noise
    left = gaussian_filter1d(first_signal.astype(float), sigma=1)
    right = gaussian_filter1d(second_signal.astype(float), sigma=1)

    # Search over possible shifts
    best_disp = 0
    max_ncc = -1.0
    # Try shifts from -max_shift to +max_shift
    max_shift = 100
    for disp in range(-max_shift, max_shift + 1):
        if disp < 0:
            s1 = left[-disp:]
            s2 = right[: len(s1)]
        else:
            s1 = left[: len(left) - disp]
            s2 = right[disp : disp + len(s1)]
        if len(s1) < 10:
            continue
        # Compute NCC
        corr = np.dot(s1, s2)
        norm = np.linalg.norm(s1) * np.linalg.norm(s2)
        ncc = corr / (norm + 1e-8)
        if ncc > max_ncc:
            max_ncc = ncc
            best_disp = disp
    return best_disp, max_ncc
