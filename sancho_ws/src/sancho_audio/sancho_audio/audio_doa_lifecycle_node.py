import math
import numpy as np

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.qos import QoSProfile

from std_msgs.msg import Float32
from hri_msgs.msg import ChunkStereo

from .utils.doa import DOAMethod, GCCPHATDOA, NCCDOA, DOA_METHODS


def next_pow2(n):
    """Next power of 2"""
    return 1 << (int(n - 1).bit_length())


def hann_window(n):
    """Aperiodic Hann window"""
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)


def bandpass_rect_fft(x, fs, low_hz, high_hz):
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


class AudioDOALifecycleNode(LifecycleNode):
    """DOA estimation with 2 mics. Can use GCC-PHAT or NCC"""

    def __init__(self):
        super().__init__("audio_doa")

        self.declare_parameters(namespace='', parameters={
            ("mic_topic", "sancho_audio/microphone/stereo"),
            ("doa_topic", "sancho_audio/doa"),
            ("mic_distance", 0.1225),           # m
            ("doa_method", DOA_METHODS.NCC),
            ("enable_bandpass", True),
            ("lowcut_hz", 300.0),
            ("highcut_hz", 3400.0),
            ("min_energy_dbfs", -40.0),
            ("min_peak_ratio", 6.0),            # usado por GCC-PHAT
            ("no_speech_value", float("nan")),
        })

        self.sub_mic = None
        self.pub_angle = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo de DOA...")

        self.mic_topic = self.get_parameter("mic_topic").value
        self.doa_topic = self.get_parameter("doa_topic").value
        self.enable_bp = self.get_parameter("enable_bandpass").value
        self.low_hz = self.get_parameter("lowcut_hz").value
        self.high_hz = self.get_parameter("highcut_hz").value
        self.min_dbfs = self.get_parameter("min_energy_dbfs").value
        self.min_peak_ratio = self.get_parameter("min_peak_ratio").value
        self.no_speech_value = self.get_parameter("no_speech_value").value
        self.doa_method = self.get_parameter("doa_method").value
        self.d = self.get_parameter("mic_distance").value

        self.doa_methods: dict[str, DOAMethod] = {
            DOA_METHODS.GCC_PHAT: GCCPHATDOA(self.d, self.min_peak_ratio),
            DOA_METHODS.NCC: NCCDOA(self.d)
        }

        qos = QoSProfile(depth=10)
        self.pub_angle = self.create_lifecycle_publisher(Float32, self.doa_topic, qos)

        self.get_logger().info(f"Modo seleccionado: {self.doa_method}")

        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo de DOA...")

        qos = QoSProfile(depth=10)
        self.sub_mic = self.create_subscription(ChunkStereo, self.mic_topic, self.on_chunk, qos)

        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo de DOA...")

        if self.sub_mic:
            self.destroy_subscription(self.sub_mic)
            self.sub_mic = None

        return super().on_deactivate(state)

    def on_chunk(self, msg: ChunkStereo):
        """Procesa cada chunk estéreo, estima DOA y publica el ángulo"""
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

            # Hann window
            w = hann_window(n).astype(np.float32)
            Lw = L * w
            Rw = R * w

            # Bandpass opcional
            if self.enable_bp and self.high_hz < fs * 0.5 and self.low_hz < self.high_hz:
                Lw = bandpass_rect_fft(Lw, fs, self.low_hz, self.high_hz)
                Rw = bandpass_rect_fft(Rw, fs, self.low_hz, self.high_hz)

            # VAD simple por energía
            eps = 1e-12
            rms = math.sqrt(float(np.mean(0.5 * (Lw * Lw + Rw * Rw)) + eps))
            dbfs = 20.0 * math.log10(max(rms, eps))
            if dbfs < self.min_dbfs:
                self.pub_angle.publish(Float32(data=float(self.no_speech_value)))
                return

            # Selección del método
            angle_deg = self.doa_methods[self.doa_method].calc_doa(Lw, Rw, fs)
            self.get_logger().info(f"angulo: {angle_deg}")
            self.pub_angle.publish(Float32(data=float(angle_deg)))

        except Exception as e:
            self.get_logger().warn(f"Processing angle error: {e}")


def main(args=None):
    rclpy.init(args=args)
    lifecycle_node = AudioDOALifecycleNode()
    rclpy.spin(lifecycle_node)
    rclpy.shutdown()
