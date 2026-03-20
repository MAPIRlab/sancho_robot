import time
from enum import Enum
import numpy as np

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from std_msgs.msg import String
from sancho_interfaces.msg import ChunkMono
from sancho_interfaces.srv import STT

IMPORTS_SUCCESSFUL = True
IMPORT_ERROR_MSG = ""

try:
    from .utils.silero_vad_attach_criterion import SileroVADAttachCriterion
    from .utils.intensity_attach_criterion import IntensityAttachCriterion
except ImportError as e:
    IMPORTS_SUCCESSFUL = False
    IMPORT_ERROR_MSG = str(e)


class AudioState(int, Enum):
    NO_AUDIO = -1
    SOME_AUDIO = 0
    END_AUDIO = 1


class VADTranscriptorNode(LifecycleNode):
    """
    Listens to the microphone when active, groups audio using VAD,
    and sends it to the STT service once the user finishes speaking.
    """
    def __init__(self):
        super().__init__("vad_transcriptor")

        self.declare_parameter("mic_topic", "/sancho_audio/microphone/mono")
        self.declare_parameter("transcription_topic", "/voice_events/user_transcription")
        self.declare_parameter("vad_criterion", "intensity")
        self.declare_parameter("intensity_threshold", 900)
        self.declare_parameter("timeout_seconds", 5.0)
        self.declare_parameter("chunk_size", 0.5)
        self.declare_parameter("silence_patience_seconds", 1.5)

        self.audio_state = AudioState.NO_AUDIO
        self.audio_buffer = []
        self.check_audio_buffer = []
        self.previous_chunk = []
        self.start_listening_time = 0.0
        self.silence_timer = 0.0
        
        # Bandera para ignorar audio mientras esperamos respuesta del STT
        self._processing = False

        self.chunk_attach_criterion = None
        self.transcription_pub = None
        self.mic_sub = None
        self.stt_client = None

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring VAD Transcriptor...")
        if not IMPORTS_SUCCESSFUL:
            self.get_logger().fatal(f"Could not import VAD models: {IMPORT_ERROR_MSG}")
            return TransitionCallbackReturn.FAILURE

        criterion = self.get_parameter("vad_criterion").get_parameter_value().string_value
        threshold = self.get_parameter("intensity_threshold").get_parameter_value().integer_value

        if criterion == "intensity":
            self.chunk_attach_criterion = IntensityAttachCriterion(threshold)
        elif criterion == "silero":
            self.chunk_attach_criterion = SileroVADAttachCriterion()
        else:
            self.get_logger().error(f"Unrecognized criterion: {criterion}")
            return TransitionCallbackReturn.FAILURE

        transcription_topic = self.get_parameter("transcription_topic").get_parameter_value().string_value
        self.transcription_pub = self.create_lifecycle_publisher(String, transcription_topic, 10)
        self.stt_client = self.create_client(STT, 'sancho_hri/speech/stt')

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> LISTENING FOR VOICE COMMAND <<<")
        self._processing = False
        self.start_listening_time = time.time()
        self.audio_state = AudioState.NO_AUDIO
        self.audio_buffer = []
        self.check_audio_buffer = []
        self.previous_chunk = []
        self.silence_timer = 0.0

        mic_topic = self.get_parameter("mic_topic").get_parameter_value().string_value
        self.mic_sub = self.create_subscription(ChunkMono, mic_topic, self.on_audio_chunk, 10)

        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> VAD TRANSCRIPTOR DEACTIVATED <<<")
        if self.mic_sub:
            self.destroy_subscription(self.mic_sub)
            self.mic_sub = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        if self.transcription_pub:
            self.destroy_publisher(self.transcription_pub)
        self.chunk_attach_criterion = None
        return TransitionCallbackReturn.SUCCESS

    def on_audio_chunk(self, msg: ChunkMono):
        if self._processing:
            return

        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate
        self.check_audio_buffer.extend(new_audio)

        timeout = self.get_parameter("timeout_seconds").get_parameter_value().double_value
        chunk_size = self.get_parameter("chunk_size").get_parameter_value().double_value

        # Timeout check
        if len(self.audio_buffer) == 0 and (time.time() - self.start_listening_time) > timeout:
            self.get_logger().warn("Timeout: No voice detected.")
            self._publish_transcription("")
            self._processing = True
            return

        # VAD grouping logic
        if len(self.check_audio_buffer) >= (chunk_size * sample_rate):
            # Someone talked
            if self.chunk_attach_criterion.should_attach_chunk(self.check_audio_buffer, sample_rate):
                self.silence_timer = 0.0
                
                if self.audio_state == AudioState.NO_AUDIO:
                    self.audio_state = AudioState.SOME_AUDIO
                    self.audio_buffer.extend(self.previous_chunk)

                self.audio_buffer.extend(self.check_audio_buffer)
                self.get_logger().debug(f"Voice detected. Buffer: {len(self.audio_buffer) / sample_rate:.1f}s")
            
            # Silence
            elif self.audio_state != AudioState.NO_AUDIO:
                self.audio_buffer.extend(self.check_audio_buffer)
                self.silence_timer += chunk_size
                
                patience = self.get_parameter("silence_patience_seconds").get_parameter_value().double_value
                
                # Silence patience exceeded
                if self.silence_timer >= patience:
                    self.audio_state = AudioState.END_AUDIO
                    self.get_logger().info("End of speech detected (Silence patience reached).")

            self.previous_chunk = self.check_audio_buffer
            self.check_audio_buffer = []

        if self.audio_state == AudioState.END_AUDIO:
            self._processing = True
            self._process_stt(self.audio_buffer, sample_rate)

    def _process_stt(self, audio_data, sample_rate):
        if not self.stt_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().error("STT service not available.")
            self._publish_transcription("")
            return

        req = STT.Request()
        req.audio = list(map(int, audio_data))
        req.sample_rate = sample_rate

        self.get_logger().info(f"Sending {len(audio_data)/sample_rate:.1f}s of audio to STT...")
        future = self.stt_client.call_async(req)
        future.add_done_callback(self._stt_callback)

    def _stt_callback(self, future):
        try:
            response = future.result()
            transcribed_text = response.text
            self.get_logger().info(f"[SUCCESS] Transcription: '{transcribed_text}'")
            self._publish_transcription(transcribed_text)
        except Exception as e:
            self.get_logger().error(f"STT request failed: {e}")
            self._publish_transcription("")

    def _publish_transcription(self, text):
        msg = String()
        msg.data = text
        self.transcription_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = VADTranscriptorNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()