import re
import subprocess

import rclpy
from rclpy.qos import QoSProfile
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from std_msgs.msg import Float32


class AudioDOAXVF3800LifecycleNode(LifecycleNode):

    def __init__(self):
        super().__init__("audio_doa_xvf3800")
        
        self.declare_parameters(namespace='', parameters={
            ("doa_topic", "sancho_audio/doa"),                  # tópico Float32 con grados
            ("poll_hz", 10.0),                                  # frecuencia de sondeo
            ("no_speech_value", float("nan")),                  # valor cuando no hay voz/ángulo
        })

        self.pub_angle = None
        self.timer = None

        self._deg_re = re.compile(r"\((nan|[-+]?\d+(?:\.\d+)?)\s+deg\)", flags=re.I) # Para sacar el ángulo procesado

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo AudioDOAXVF3800LifecycleNode.")

        self.doa_topic = self.get_parameter("doa_topic").value
        self.poll_hz = float(self.get_parameter("poll_hz").value)
        self.no_speech_value = float(self.get_parameter("no_speech_value").value)

        if self.poll_hz <= 0.0:
            self.get_logger().warn("poll_hz <= 0. Ajustando a 1.0 Hz.")
            self.poll_hz = 1.0

        qos = QoSProfile(depth=10)
        self.pub_angle = self.create_lifecycle_publisher(Float32, self.doa_topic, qos)

        self.get_logger().info(f"Publicará en '{self.doa_topic}' a {self.poll_hz:.2f} Hz.")

        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo AudioDOAXVF3800LifecycleNode.")

        period = 1.0 / self.poll_hz
        self.timer = self.create_timer(period, self.spin)

        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo AudioDOAXVF3800LifecycleNode.")

        if self.timer is not None:
            self.destroy_timer(self.timer)
            self.timer = None

        return super().on_deactivate(state)

    def spin(self):
        angle = self._read_processed_deg()

        if angle is None:
            self.pub_angle.publish(Float32(data=self.no_speech_value))
            self.get_logger().debug("Sin voz (publicado NaN).")
        else:
            angle = float(angle) % 360.0
            self.pub_angle.publish(Float32(data=angle))
            self.get_logger().info(f"DoA (processed): {angle:6.2f}°")

    def _read_processed_deg(self):
        try:
            out = subprocess.check_output(["xvf_host", "AUDIO_MGR_SELECTED_AZIMUTHS"], text=True)
        except subprocess.CalledProcessError as e:
            self.get_logger().warn(f"Error invocando comando: {e}")
            return None
        except FileNotFoundError:
            self.get_logger().error(f"No se encontró el ejecutable '{self.cmd[0]}'.")
            return None

        matches = self._deg_re.findall(out)
        if not matches:
            self.get_logger().debug("No se encontraron grados en la salida del comando.")
            return None

        val = matches[0]  # 1º = processed (en grados)
        if isinstance(val, tuple):
            val = val[0]
        if str(val).lower() == "nan":
            return None

        try:
            return float(val)
        except ValueError:
            return None


def main(args=None):
    rclpy.init(args=args)
    node = AudioDOAXVF3800LifecycleNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
