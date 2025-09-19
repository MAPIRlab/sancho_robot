import numpy as np
from .doa_method import DOAMethod


class GCCPHATDOA(DOAMethod):
    """DOA por GCC-PHAT para dos micrófonos (izq, der)"""

    def __init__(self, mic_distance_m, min_peak_ratio):
        self.mic_distance_m = mic_distance_m
        self.min_peak_ratio = min_peak_ratio

    def calc_doa(self, left_mic, right_mic, sample_rate, refine_parabolic=True):
        """Devuelve el ángulo en grados en [-90, 90]; si no es fiable, devuelve NaN"""

        if left_mic is None or right_mic is None or sample_rate is None:
            return float("nan")
        n = min(len(left_mic), len(right_mic))
        if n < 16 or sample_rate <= 0:
            return float("nan")

        x = np.asarray(left_mic[:n], dtype=float)
        y = np.asarray(right_mic[:n], dtype=float)

        tdoa, lag_refined, cc, lags = self.gcc_phat(x, y, sample_rate, refine_parabolic=refine_parabolic)

        if cc.size == 0:
            return float("nan")
        peak = float(np.max(cc))
        mean_abs = float(np.mean(np.abs(cc)) + 1e-12)
        peak_ratio = peak / mean_abs
        if not np.isfinite(peak_ratio) or peak_ratio < float(self.min_peak_ratio):
            return float("nan")

        c = 343.2
        d = float(self.mic_distance_m)
        tdoa = float(np.clip(tdoa, -d / c, d / c))

        xsin = (c * tdoa) / d
        if abs(xsin) > 1.05:
            return float("nan")
        xsin = float(np.clip(xsin, -1.0, 1.0))

        angle_deg = float(np.degrees(np.arcsin(xsin)))
        
        return angle_deg

    def gcc_phat(self, x, y, fs, nfft_policy="2x_next_pow2", refine_parabolic=True):
        """GCC-PHAT con interpolación parabólica opcional"""

        n = int(min(len(x), len(y)))
        if n <= 1:
            return 0.0, 0.0, np.zeros(0, dtype=float), np.zeros(0, dtype=int)

        n_fft = self.choose_nfft(n, nfft_policy)
        X = np.fft.rfft(x, n=n_fft)
        Y = np.fft.rfft(y, n=n_fft)

        R = X * np.conj(Y)
        denom = np.abs(R)
        denom[denom == 0.0] = 1e-12
        R_phat = R / denom

        cc_full = np.fft.irfft(R_phat, n=n_fft)
        max_shift = n - 1
        cc = np.concatenate((cc_full[-max_shift:], cc_full[:max_shift + 1]))
        lags = np.arange(-max_shift, max_shift + 1, dtype=np.int64)

        peak_idx = int(np.argmax(cc))
        peak_lag = float(lags[peak_idx])
        lag_refined = peak_lag

        if refine_parabolic and 0 < peak_idx < len(cc) - 1:
            y0, y1, y2 = cc[peak_idx - 1], cc[peak_idx], cc[peak_idx + 1]
            denom_q = 2.0 * (y0 - 2.0 * y1 + y2)
            if abs(denom_q) > 1e-12:
                delta = (y0 - y2) / denom_q
                lag_refined = peak_lag + float(delta)

        tdoa = lag_refined / float(fs)
        return float(tdoa), float(lag_refined), cc.astype(float, copy=False), lags

    def choose_nfft(self, n, policy):
        """Selecciona tamaño de FFT según política"""
        if policy == "2x_next_pow2":
            return self.next_pow2(2 * n)
        elif policy == "next_pow2":
            return self.next_pow2(n)
        elif policy == "exact":
            return max(1, int(n))
        else:
            return self.next_pow2(2 * n)

    def next_pow2(self, n):
        """Siguiente potencia de 2"""
        return 1 << (int(n - 1).bit_length())
