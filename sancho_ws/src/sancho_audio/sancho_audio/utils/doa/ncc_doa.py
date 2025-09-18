import numpy as np
from scipy.ndimage import gaussian_filter1d
from .doa_method import DOAMethod


class NCCDOA(DOAMethod):
    """DOA por NCC para dos micrófonos (izq, der)"""

    def __init__(self, mic_distance_m=0.1225):
        self.mic_distance_m = mic_distance_m

    def calc_doa(self, left_mic, right_mic, sample_rate, smooth_sigma=1.0, threshold_samples=10, stride=2, min_ncc= 0.1):
        """Devuelve el ángulo en grados en [-90, 90]. Si no hay voz o algo raro, devuelve NaN"""

        if left_mic is None or right_mic is None or sample_rate is None:
            print("mics none")
            return float("nan")
        
        n = min(len(left_mic), len(right_mic))
        if n < 16:
            print("16", n)
            return float("nan")

        left_f = np.asarray(left_mic[:n], dtype=float)
        right_f = np.asarray(right_mic[:n], dtype=float)
        if smooth_sigma and smooth_sigma > 0:
            left_f = gaussian_filter1d(left_f, smooth_sigma)
            right_f = gaussian_filter1d(right_f, smooth_sigma)

        _, max_ncc, best_displacement = self.determine_audio_location(left_f, right_f, sample_rate,
            smooth_sigma=0.0, threshold_samples=threshold_samples, stride=stride, min_ncc=min_ncc)

        print(max_ncc)
        if max_ncc < min_ncc:
            print("ncc baito")
            return float("nan")

        time_variation = -best_displacement / sample_rate # seconds
        sin_degree = ((343.2 * time_variation) / self.mic_distance_m)
        print("sin_degree", sin_degree)
        sin_degree = 1 if sin_degree > 1 else (-1 if sin_degree < -1 else sin_degree)
        # lo de arriba funciona, es lo antiguio, lo de abajo lo de chatgpt, no va
        #tdoa_s = -best_displacement / sample_rate
        #x = (sample_rate * tdoa_s) / self.mic_distance_m  # sin(theta)

        if abs(x) > 1.05: # Comprobación estricta de validez física
            print("sin", x, sample_rate, best_displacement, self.mic_distance_m)
            return float("nan")
        x = np.clip(x, -1.0, 1.0)
        print("x", x)
        print("arcsin", np.arcsin(x))
        angle_deg = np.degrees(np.arcsin(x))
        print("angle", angle_deg)
        return angle_deg

    def determine_audio_location(self, microphone_left, microphone_right, sample_rate, smooth_sigma=1.0, threshold_samples=10, stride=2, min_ncc=0.1):
        """Calcula la localización del sonido a partir de dos microfonos"""

        left_f = np.asarray(microphone_left, dtype=float)
        right_f = np.asarray(microphone_right, dtype=float)

        if smooth_sigma and smooth_sigma > 0:
            left_f = gaussian_filter1d(left_f, smooth_sigma)
            right_f = gaussian_filter1d(right_f, smooth_sigma)

        L = min(len(left_f), len(right_f))
        if L <= 1:
            return "Center", 0.0, 0

        if sample_rate is not None and sample_rate > 0:
            max_shift = int(np.floor((self.mic_distance_m / 343.2) * sample_rate))
            max_shift = max(1, min(max_shift, (L - 1)))  # seguro y físico
        else:
            max_shift = max(1, (L - 1) // 2)

        bl, nl = self.calculate_best_left_shift(max_shift, left_f, right_f, stride=max(1, int(stride)))
        br, nr = self.calculate_best_left_shift(max_shift, right_f, left_f, stride=max(1, int(stride)))

        if nl >= nr:
            best_displacement, max_ncc = -bl, nl
        else:
            best_displacement, max_ncc = br, nr
        
        if not np.isfinite(max_ncc) or max_ncc < min_ncc:
            return "Center", max_ncc if np.isfinite(max_ncc) else 0.0, 0

        direction = (
            "Left" if best_displacement < -threshold_samples else
            ("Right" if best_displacement > threshold_samples else "Center")
        )

        return direction, max_ncc, best_displacement

    def normalized_cross_correlation(self, first_signal, second_signal):
        """NCC robusta (sustracción de media, evita división por cero)"""

        n = min(len(first_signal), len(second_signal))
        if n <= 0:
            return 0.0
        a = first_signal[:n] - np.mean(first_signal[:n])
        b = second_signal[:n] - np.mean(second_signal[:n])
        normA = np.linalg.norm(a)
        normB = np.linalg.norm(b)
        if normA == 0.0 or normB == 0.0:
            return 0.0
        cross = np.correlate(a, b, mode='valid')[0]

        return float(cross / (normA * normB))

    def calculate_best_left_shift(self, max_shift, first_signal, second_signal, stride=2):
        """Desplaza 'first_signal' hacia la izquierda respecto a 'second_signal' y devuelve el desplazamiento que maximiza la NCC"""

        best_displacement, max_ncc = 0, -1.0
        stride = max(1, int(stride))
        L = min(len(first_signal), len(second_signal))
        for i in range(0, min(max_shift, L - 1) + 1, stride):
            sf = first_signal[i:]
            ss = second_signal[:len(second_signal) - i]
            if len(sf) <= 1 or len(ss) <= 1:
                break
            ncc = self.normalized_cross_correlation(sf, ss)
            if ncc > max_ncc:
                best_displacement = i
                max_ncc = ncc

        return best_displacement, max_ncc