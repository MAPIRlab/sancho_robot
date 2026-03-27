import re
import subprocess

import rclpy
from rclpy.qos import QoSProfile
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from std_msgs.msg import Float32


class AudioDOAXVF3800LifecycleNode(LifecycleNode):

    def __init__(self):
        super().__init__("audio_doa_xvf3800")
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/audio_doa_xvf3800_lifecycle_node.py

=======
        
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/audio_doa_xvf3800_lifecycle_node.py
        self.declare_parameter("doa_topic", "sancho_audio/doa")
        self.declare_parameter("poll_hz", 10.0)

        self.pub_angle = None
        self.timer = None

        # RE used to get angle from command output
        self._deg_re = re.compile(r"\((nan|[-+]?\d+(?:\.\d+)?)\s+deg\)", flags=re.I)

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo AudioDOAXVF3800LifecycleNode.")

        self.doa_topic = self.get_parameter("doa_topic").value
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/audio_doa_xvf3800_lifecycle_node.py
        self.poll_hz = self.get_parameter("poll_hz").get_parameter_value().double_value
=======
        self.poll_hz = float(self.get_parameter("poll_hz").value)
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/audio_doa_xvf3800_lifecycle_node.py

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
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/audio_doa_xvf3800_lifecycle_node.py
        if angle:
            angle = 180 - angle
            self.get_logger().info(f"DoA: {angle:6.2f}°")
            if self.pub_angle:
                self.pub_angle.publish(Float32(data=angle))
        else:
            self.get_logger().info("No angle")

=======

        if angle:
            angle = ((float(angle) + 180) % 360) - 180
            self.get_logger().info(f"DoA (processed): {angle:6.2f}°")
            self.pub_angle.publish(Float32(data=angle))
        else:
            self.get_logger().info("No angle")
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/audio_doa_xvf3800_lifecycle_node.py

    def _read_processed_deg(self):
        cmd = ["xvf_host", "AUDIO_MGR_SELECTED_AZIMUTHS"]

        try:
            out = subprocess.check_output(cmd, text=True)
        except subprocess.CalledProcessError as e:
            self.get_logger().warn(f"Error invocando comando: {e}")
            return None
        except FileNotFoundError:
            self.get_logger().error(f"No se encontró el ejecutable '{cmd[0]}'.")
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
