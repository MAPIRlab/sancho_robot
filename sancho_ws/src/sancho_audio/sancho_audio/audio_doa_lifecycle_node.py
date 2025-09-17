import math
from typing import Tuple

import numpy as np

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.qos import QoSProfile

from std_msgs.msg import Float32
from hri_msgs.msg import ChunkStereo


def next_pow2(n: int) -> int:
    """Next power of 2"""
    return 1 << (int(n - 1).bit_length())

def hann_window(n: int) -> np.ndarray:
    """Aperiodic Hann window"""
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)

def bandpass_rect_fft(x: np.ndarray, fs: float, low_hz: float, high_hz: float) -> np.ndarray:
    """Rectangular frequency filter to center in voice"""
    n = len(x)
    
    n_fft = next_pow2(n)
    X = np.fft.rfft(x, n=n_fft)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs)  
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    Xf = np.zeros_like(X) 
    Xf[mask] = X[mask]
    xf = np.fft.irfft(Xf, n=n_fft)[:n]
    return xf


def gcc_phat(x: np.ndarray, y: np.ndarray, fs: float) -> Tuple[float, float, np.ndarray, np.ndarray]:
    """GCC-PHAT that returns tdoa_s, lag_ref_samples, cc and lags"""
    n = len(x)
    n_fft = next_pow2(2 * n)  # zero-padding
    X = np.fft.rfft(x, n=n_fft)
    Y = np.fft.rfft(y, n=n_fft)
    R = X * np.conj(Y)
    denom = np.abs(R)
    denom[denom == 0.0] = 1e-12
    R_phat = R / denom


    cc_full = np.fft.irfft(R_phat, n=n_fft)
    max_shift = n - 1
    cc = np.concatenate((cc_full[-max_shift:], cc_full[: max_shift + 1]))
    lags = np.arange(-max_shift, max_shift + 1, dtype=np.int64)

    peak_idx = int(np.argmax(cc))
    peak_lag = float(lags[peak_idx])

    lag_refined = peak_lag
    if 0 < peak_idx < len(cc) - 1:
        y0, y1, y2 = cc[peak_idx - 1], cc[peak_idx], cc[peak_idx + 1]
        denom_q = 2.0 * (y0 - 2.0 * y1 + y2)
        if abs(denom_q) > 1e-12:
            delta = (y0 - y2) / denom_q
            lag_refined = peak_lag + delta

    tdoa = lag_refined / fs
    return tdoa, lag_refined, cc, lags


class AudioDOALifecycleNode(LifecycleNode):
    """DOA estimation with 2 mics. Uses FFT + Hann Window, vocal-band filtering (300-3400 Hz), GCC-PHAT and parabolic interpolation"""

    def __init__(self):
        super().__init__("audio_doa")

        self.declare_parameters(namespace='', parameters={
            ("mic_distance", 0.1225),           # m
            ("speed_of_sound", 343.0),          # m/s | To improve with temperature sensor
            ("enable_bandpass", True),
            ("lowcut_hz", 300.0),
            ("highcut_hz", 3400.0),
            ("min_energy_dbfs", -40.0),         # VAD: umbral de energía
            ("min_peak_ratio", 6.0),            # pico/medio mínimo en correlación PHAT
            ("no_speech_value", float("nan")),  # valor a publicar si no hay voz (p.ej., -180.0 o NaN)
        })

        self.sub_mic = None
        self.pub_angle =None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo de DOA...")

        self.d = self.get_parameter("mic_distance").value
        self.c = self.get_parameter("speed_of_sound").value
        self.enable_bp = self.get_parameter("enable_bandpass").value
        self.low_hz = self.get_parameter("lowcut_hz").value
        self.high_hz = self.get_parameter("highcut_hz").value
        self.min_dbfs = self.get_parameter("min_energy_dbfs").value
        self.min_peak_ratio = self.get_parameter("min_peak_ratio").value
        self.no_speech_value = self.get_parameter("no_speech_value").value

        qos = QoSProfile(depth=10)
        self.pub_angle = self.create_lifecycle_publisher(Float32, "sancho_audio/doa", qos)

        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo de DOA...")

        qos = QoSProfile(depth=10)
        self.sub_mic = self.create_subscription(ChunkStereo, "sancho_audio/microphone/stereo", self.on_chunk, qos)

        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo de DOA...")

        if self.sub_mic:
            self.destroy_subscription(self.sub_mic)
            self.sub_mic = None

        return super().on_deactivate(state)

    def on_chunk(self, msg: ChunkStereo):
        try:
            fs = float(msg.sample_rate)
            if fs <= 0.0:
                return
            
            L = np.asarray(msg.chunk_left, dtype=np.float32) / 32768.0
            R = np.asarray(msg.chunk_right, dtype=np.float32) / 32768.0
            n = min(len(L), len(R))
            if n <= 16:
                return
            L = L[:n]
            R = R[:n]

            w = hann_window(n).astype(np.float32)
            Lw = L * w
            Rw = R * w

            if self.enable_bp and self.high_hz < fs * 0.5 and self.low_hz < self.high_hz:
                Lw = bandpass_rect_fft(Lw, fs, self.low_hz, self.high_hz)
                Rw = bandpass_rect_fft(Rw, fs, self.low_hz, self.high_hz)

            eps = 1e-12
            rms = math.sqrt(float(np.mean(0.5 * (Lw * Lw + Rw * Rw)) + eps))
            dbfs = 20.0 * math.log10(max(rms, eps))
            if dbfs < self.min_dbfs:
                self.pub_angle.publish(Float32(data=float(self.no_speech_value)))
                return

            tdoa, _, cc, _ = gcc_phat(Lw, Rw, fs)

            peak = float(np.max(cc))
            mean_abs = float(np.mean(np.abs(cc)) + 1e-12)
            peak_ratio = peak / mean_abs
            if not np.isfinite(peak_ratio) or peak_ratio < self.min_peak_ratio:
                self.pub_angle.publish(Float32(data=float(self.no_speech_value)))
                return

            tdoa_max = self.d / self.c
            tdoa = float(np.clip(tdoa, -tdoa_max, tdoa_max))

            sin_arg = (self.c * tdoa) / self.d
            sin_arg = float(np.clip(sin_arg, -1.0, 1.0))
            theta_deg = math.degrees(math.asin(sin_arg))

            self.pub_angle.publish(Float32(data=float(theta_deg)))

        except Exception as e:
            self.get_logger().warn(f"Processing angle error: {e}")

def main(args=None):
    rclpy.init(args=args)
    lifecycle_node = AudioDOALifecycleNode()
    rclpy.spin(lifecycle_node)
    rclpy.shutdown()
