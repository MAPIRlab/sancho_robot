import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
import numpy as np

from std_msgs.msg import Empty
from sancho_interfaces.msg import ChunkMono

try:
    from .utils.openwakeword_hotword import OpenWakeWordHotword
except ImportError as e:
    print(f"Failed to import hotword model: {e}")


class HotwordDetectorNode(LifecycleNode):
    """
    Listens to the microphone topic when ACTIVE and sends an event 
    message whenever the configured hotword is said.
    """
    def __init__(self):
        super().__init__("hotword_detector")

        self.declare_parameter("mic_topic", "/sancho_audio/microphone/mono")
        self.declare_parameter("hotword_event_topic", "/voice_events/hotword_detected")

        self.hotword_detector = None
        self._mic_sub = None
        self._event_pub = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        try:
            self.get_logger().info("Configuring Hotword Detector (loading model)...")
            self.hotword_detector = OpenWakeWordHotword()
            
            event_topic = self.get_parameter("hotword_event_topic").get_parameter_value().string_value
            self._event_pub = self.create_lifecycle_publisher(Empty, event_topic, 10)
            
            return TransitionCallbackReturn.SUCCESS
        except Exception as e:
            print(f"Error al configurar Hotword Detector: {e}")
            return TransitionCallbackReturn.FAILURE

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> HOTWORD DETECTOR ACTIVATED <<<")
        
        # Nos suscribimos al micrófono solo cuando estamos activos
        mic_topic = self.get_parameter("mic_topic").get_parameter_value().string_value
        self._mic_sub = self.create_subscription(ChunkMono, mic_topic, self.on_audio_chunk, 10)
        
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> HOTWORD DETECTOR DEACTIVATED <<<")
        
        # Destruimos la suscripción para dejar de procesar audio
        if self._mic_sub:
            self.destroy_subscription(self._mic_sub)
            self._mic_sub = None
            
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        if self._event_pub:
            self.destroy_publisher(self._event_pub)
        self.hotword_detector = None
        return TransitionCallbackReturn.SUCCESS

    def on_audio_chunk(self, msg: ChunkMono):
        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate

        if self.hotword_detector.detect(new_audio, sample_rate):
            self.get_logger().info("¡Hotword detected!")
            self._event_pub.publish(Empty())


def main(args=None):
    rclpy.init(args=args)
    node = HotwordDetectorNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()