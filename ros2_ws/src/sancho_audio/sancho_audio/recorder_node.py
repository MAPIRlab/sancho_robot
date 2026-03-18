import os
import wave
import numpy as np

import rclpy
from rclpy.node import Node
from sancho_interfaces.msg import ChunkMono, ChunkStereo

OUTPUT_PATH = "tests/record_test.wav"

def rms_dbfs_int16(x: np.ndarray) -> float:
    """RMS en dBFS para señal int16 (±32768)."""
    if x.size == 0:
        return float("-inf")
    x = x.astype(np.float32)
    rms = np.sqrt(np.mean(x * x))
    # evitar log(0)
    rms = max(rms, 1e-9)
    dbfs = 20.0 * np.log10(rms / 32768.0)
    return float(dbfs)

class RecorderNode(Node):
    def __init__(self):
        super().__init__("recorder_node")
        self.declare_parameter("source", "mono")              # "mono" | "stereo"
        self.declare_parameter("target_duration_sec", 10)     # segundos
        self.declare_parameter("print_dbfs", True)            # imprimir RMS por chunk
        self.declare_parameter("silence_dbfs", -50.0)         # umbral para etiquetar "silencio"

        self.source = self.get_parameter("source").get_parameter_value().string_value.lower()
        self.target_duration = int(self.get_parameter("target_duration_sec").get_parameter_value().integer_value or 10)
        self.print_dbfs = bool(self.get_parameter("print_dbfs").get_parameter_value().bool_value)
        self.silence_dbfs = float(self.get_parameter("silence_dbfs").get_parameter_value().double_value)

        self.sample_rate = None
        self.n_channels = 1 if self.source == "mono" else 2
        self.frames_needed = None
        self.buffer = []  # numpy int16 interleaved
        self.done_future = rclpy.Future()

        if self.source == "stereo":
            self.sub = self.create_subscription(ChunkStereo, "sancho_audio/microphone/stereo", self.cb_stereo, 10)
        else:
            self.sub = self.create_subscription(ChunkMono, "sancho_audio/microphone/mono", self.cb_mono, 10)

        self.get_logger().info(f"Recorder: source={self.source}, dur={self.target_duration}s")

    def ensure_sr(self, sr):
        if self.sample_rate is None and sr > 0:
            self.sample_rate = int(sr)
            self.frames_needed = self.sample_rate * self.target_duration
            self.get_logger().info(f"sample_rate={self.sample_rate} Hz | frames_needed={self.frames_needed}")

    def cb_mono(self, msg: ChunkMono):
        self.ensure_sr(msg.sample_rate)
        if self.sample_rate is None:
            return
        x = np.asarray(msg.chunk_mono, dtype=np.int16)
        if x.size:
            # Print RMS (dBFS) por chunk
            if self.print_dbfs:
                db = rms_dbfs_int16(x)
                tag = "silencio" if db <= self.silence_dbfs else "voz?"
                self.get_logger().info(f"[mono] chunk={x.size} samples  RMS={db:6.1f} dBFS  [{tag}]")
            self.buffer.append(x)
            self.maybe_finish()

    def cb_stereo(self, msg: ChunkStereo):
        self.ensure_sr(msg.sample_rate)
        if self.sample_rate is None:
            return
        L = np.asarray(msg.chunk_left, dtype=np.int16)
        R = np.asarray(msg.chunk_right, dtype=np.int16)
        n = min(L.size, R.size)
        if n == 0:
            return

        if self.print_dbfs:
            dbl = rms_dbfs_int16(L[:n])
            dbr = rms_dbfs_int16(R[:n])
            inter = np.empty(2 * n, dtype=np.int16)
            inter[0::2] = L[:n]; inter[1::2] = R[:n]
            dbg = rms_dbfs_int16(inter)
            tag = "silencio" if max(dbl, dbr, dbg) <= self.silence_dbfs else "voz?"
            self.get_logger().info(f"[stereo] chunk={n} fr  L={dbl:6.1f} dBFS  R={dbr:6.1f} dBFS  G={dbg:6.1f} dBFS  [{tag}]")
        else:
            inter = np.empty(2 * n, dtype=np.int16)
            inter[0::2] = L[:n]; inter[1::2] = R[:n]

        # si no hemos creado inter por print, créalo aquí
        if not self.print_dbfs:
            inter = np.empty(2 * n, dtype=np.int16)
            inter[0::2] = L[:n]
            inter[1::2] = R[:n]
        self.buffer.append(inter)
        self.maybe_finish()

    def maybe_finish(self):
        if self.frames_needed is None:
            return
        total_samples = sum(arr.size for arr in self.buffer)
        frames = total_samples if self.n_channels == 1 else total_samples // 2
        if frames >= self.frames_needed:
            self.write_wav()

    def write_wav(self):
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        data = np.concatenate(self.buffer) if self.buffer else np.zeros(0, dtype=np.int16)
        if self.n_channels == 2 and (data.size % 2 != 0):
            data = data[:-1]
        with wave.open(OUTPUT_PATH, "wb") as wf:
            wf.setnchannels(self.n_channels)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.sample_rate or 16000)
            wf.writeframes(data.tobytes())
        self.get_logger().info(f"Guardado: {OUTPUT_PATH}")
        if not self.done_future.done():
            self.done_future.set_result(True)

def main(args=None):
    rclpy.init(args=args)
    node = RecorderNode()
    rclpy.spin_until_future_complete(node, node.done_future)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
