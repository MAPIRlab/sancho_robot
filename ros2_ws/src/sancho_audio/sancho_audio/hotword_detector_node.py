import rclpy
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
from rclpy.node import Node
import numpy as np

from std_msgs.msg import Empty
from std_srvs.srv import SetBool
=======
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
import numpy as np

from std_msgs.msg import Empty
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
from sancho_interfaces.msg import ChunkMono

try:
    from .utils.openwakeword_hotword import OpenWakeWordHotword
except ImportError as e:
    print(f"Failed to import hotword model: {e}")


<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
class HotwordDetectorNode(Node):
    """
    Listens to the microphone topic and sends an event message whenever
    the configured hotword is said.
    """
    
=======
class HotwordDetectorNode(LifecycleNode):
    """
    Listens to the microphone topic when ACTIVE and sends an event 
    message whenever the configured hotword is said.
    """
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
    def __init__(self):
        super().__init__("hotword_detector")

        self.declare_parameter("mic_topic", "/sancho_audio/microphone/mono")
        self.declare_parameter("hotword_event_topic", "/voice_events/hotword_detected")

<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
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
=======
        self.hotword_detector = None
        self._mic_sub = None
        self._event_pub = None
        
        # Bandera para evitar re-detectar el eco antes de que el manager nos desactive
        self._detected = False

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
        self._detected = False
        
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
        if self._detected:
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
            return

        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate

        if self.hotword_detector.detect(new_audio, sample_rate):
            self.get_logger().info("¡Hotword detected!")
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py
            self.event_pub.publish(Empty())
            
            # Auto-desactivarse inmediatamente para no re-detectar el eco
            self._is_listening = False
=======
            self._event_pub.publish(Empty())
            
            # Bloqueamos internamente hasta que el manager llame a Deactivate
            self._detected = True
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/hotword_detector_node.py


def main(args=None):
    rclpy.init(args=args)
    node = HotwordDetectorNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()