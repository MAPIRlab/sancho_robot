import rclpy
from rclpy.node import Node
import numpy as np

from std_msgs.msg import Empty
from std_srvs.srv import SetBool
from sancho_interfaces.msg import ChunkMono

try:
    from .utils.openwakeword_hotword import OpenWakeWordHotword
except ImportError as e:
    print(f"Failed to import hotword model: {e}")


class HotwordDetectorNode(Node):
    """
    Listens to the microphone topic and sends an event message whenever
    the configured hotword is said.
    """
    
    def __init__(self):
        super().__init__("hotword_detector")

        self.declare_parameter("mic_topic", "/sancho_audio/microphone/mono")
        self.declare_parameter("hotword_event_topic", "/voice_events/hotword_detected")

        self._is_listening = False

        mic_topic = self.get_parameter("mic_topic").get_parameter_value().string_value
        event_topic = self.get_parameter("hotword_event_topic").get_parameter_value().string_value

        self.hotword_detector = OpenWakeWordHotword()

        # Suscripción y Publicador normales
        self.mic_sub = self.create_subscription(ChunkMono, mic_topic, self.on_audio_chunk, 10)
        self.event_pub = self.create_publisher(Empty, event_topic, 10)
        
        # Servicio de control (Compuerta)
        self.enable_srv = self.create_service(SetBool, '~/enable_listening', self.enable_callback)

        self.get_logger().info(f"{self.get_name()} initialized and ready.")

    def enable_callback(self, request, response):
        self._is_listening = request.data
        self.get_logger().info(f"Hotword listening state set to: {self._is_listening}")
        response.success = True
        return response

    def on_audio_chunk(self, msg: ChunkMono):
        if not self._is_listening:
            return

        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate

        if self.hotword_detector.detect(new_audio, sample_rate):
            self.get_logger().info("¡Hotword detected!")
            self.event_pub.publish(Empty())
            
            # Auto-desactivarse inmediatamente para no re-detectar el eco
            self._is_listening = False


def main(args=None):
    rclpy.init(args=args)
    node = HotwordDetectorNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()