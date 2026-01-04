#!/usr/bin/env python3
import array

import numpy as np
import pyaudio
import rclpy
from rclpy.node import Node
from std_msgs.msg import Header

from sancho_msgs.msg import AudioData
from sancho_msgs.srv import GetNoiseFloor


class MicrophoneNode(Node):
    """A ROS2 node for capturing audio from a microphone device and publishing it as AudioData messages.

    This node performs the following tasks:
    - Searches for an audio input device containing a specified string in its name
    - Captures audio data in chunks from the selected device
    - Calculates a running noise floor estimation using exponential moving average (EMA)
    - Publishes the audio data to a configurable ROS2 topic
    - Provides a service to retrieve the current noise floor value

    Parameters
    ----------
    device_search_name : str, default: "ORBBEC"
        Substring to search for in device names to find the target microphone
    chunk_size : int, default: 1024
        Number of audio frames to capture in each read operation
    topic_name : str, default: "/audio/raw"
        ROS2 topic name for publishing captured audio data
    frame_id : str, default: "microphone_frame"
        Frame ID to use in the header of published messages
    noise_floor_alpha : float, default: 0.01
        EMA coefficient for noise floor calculation (0-1, smaller = slower adaptation)

    Published Topics:
    --------------
    <topic_name> (AudioData)
        Raw audio data captured from the microphone

    Services:
    -------
    /get_noise_floor (GetNoiseFloor)
        Returns the current noise floor level estimation

    Exceptions:
    ---------
    RuntimeError
        If the specified microphone device cannot be found

    """

    def __init__(self):
        super().__init__("microphone_capturer_node")

        # 1) Declaración de parámetros
        self.declare_parameter("device_search_name", "ORBBEC")
        self.declare_parameter("chunk_size", 1024)
        self.declare_parameter("topic_name", "/audio/raw")
        self.declare_parameter("frame_id", "microphone_frame")
        self.declare_parameter("noise_floor_alpha", 0.01)

        # 2) Lectura de parámetros
        name_part = self.get_parameter("device_search_name").value
        self.chunk_size = self.get_parameter("chunk_size").value
        topic = self.get_parameter("topic_name").value
        self.frame_id = self.get_parameter("frame_id").value
        self.noise_floor_alpha = self.get_parameter("noise_floor_alpha").value

        # 3) Publisher
        self.srv = self.create_service(
            GetNoiseFloor, "/get_noise_floor", self.handle_get_noise_floor
        )
        self.pub_audio = self.create_publisher(AudioData, topic, 10)
        # Parámetro para el EMA del noise floor
        self.noise_floor = None

        # 4) Inicializar PyAudio y encontrar dispositivo
        self.pa = pyaudio.PyAudio()
        device_info = self._find_device_info(name_part)

        self.device_index = device_info["index"]
        self.sample_rate = int(device_info["defaultSampleRate"])
        self.channels = int(device_info["maxInputChannels"])

        if self.device_index is None:
            self.get_logger().error(f'Dispositivo "{name_part}" no encontrado.')
            raise RuntimeError("Micrófono no encontrado.")

        # 5) Abrir stream (excepción_on_overflow=False para robustez)
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=self.device_index,
        )
        self.get_logger().info(
            f'Stream abierto en "{name_part}" (index={self.device_index}), '
            f"{self.channels} canales @ {self.sample_rate} Hz."
        )

        # 6) Timer para leer datos periódicamente
        periodo = float(self.chunk_size) / self.sample_rate
        self.create_timer(periodo, self._timer_callback)

    def handle_get_noise_floor(self, request, response):
        """Devuelve el último noise_floor calculado."""
        if self.noise_floor is None:
            response.noise_floor = 0.0
        else:
            response.noise_floor = float(self.noise_floor)
        return response

    def _find_device_info(self, name_part: str):
        """Busca el primer dispositivo cuyo nombre contenga name_part (case-insensitive)."""
        device_info = None
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                if name_part.lower() in info.get("name", "").lower():
                    self.get_logger().info(
                        f'Dispositivo encontrado: "{info["name"]}" (index={i})'
                    )
                    device_info = info
                    break
        return device_info

    def _timer_callback(self):
        """Lee un chunk de audio y lo publica."""
        try:
            datos = self.stream.read(self.chunk_size, exception_on_overflow=False)

            # --- MÉTRICAS PARA DEBUGGING ---
            # import numpy as np
            # pcm = np.frombuffer(datos, dtype=np.int16)
            # rms  = np.sqrt(np.mean(pcm.astype(np.float32)**2))
            # peak = np.max(np.abs(pcm))
            # self.get_logger().info(
            #     f"Captured chunk → rms={rms:.1f}, peak={peak}, "
            #     f"samples={pcm.size}, sr={self.sample_rate}, ch={self.channels}"
            # )
            # -------------------------------
            # ——— Calcular energía y actualizar noise_floor EMA ———
            pcm = np.frombuffer(datos, dtype=np.int16)
            energy = float(np.mean(pcm.astype(np.int32) ** 2))
            if self.noise_floor is None:
                self.noise_floor = energy
            else:
                alfa = self.noise_floor_alpha
                self.noise_floor = alfa * energy + (1 - alfa) * self.noise_floor
            # Crear y rellenar la cabecera
            hdr = Header()
            hdr.stamp = self.get_clock().now().to_msg()
            hdr.frame_id = self.frame_id

            # Construir mensaje con cabecera
            msg = AudioData(
                header=hdr,
                sample_rate=self.sample_rate,
                channels=self.channels,
            )
            pcm_arr = array.array("h", datos)  # empaqueta los bytes en int16[]
            msg.data = pcm_arr.tolist()  # asigna la lista de int16

            self.pub_audio.publish(msg)
        except OSError as e:
            # solo catch de IOErrors (overflow, dispositivo desconectado, etc.)
            self.get_logger().warn(f"Overflow o I/O error: {e}. Reabriendo stream…")
            self._reopen_stream()
        except Exception as e:
            self.get_logger().error(f"Error inesperado al leer audio: {e}")
            self._reopen_stream()

    def _reopen_stream(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception:
            pass
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=self.device_index,
        )

    def destroy_node(self):
        """Cierre limpio del stream y PyAudio."""
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception:
            pass
        self.pa.terminate()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MicrophoneNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
