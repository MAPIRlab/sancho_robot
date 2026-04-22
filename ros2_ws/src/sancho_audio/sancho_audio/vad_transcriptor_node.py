import time
import numpy as np
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse

from sancho_interfaces.msg import ChunkMono
from sancho_interfaces.srv import STT
from sancho_interfaces.action import ListenVoice

# (Keep your existing IMPORTS_SUCCESSFUL / try-except block here)
try:
    from .utils.silero_vad_attach_criterion import SileroVADAttachCriterion
    from .utils.intensity_attach_criterion import IntensityAttachCriterion
except ImportError as e:
    pass

class AudioState(int, Enum):
    NO_AUDIO = -1
    SOME_AUDIO = 0
    END_AUDIO = 1

class VADTranscriptorActionServer(Node):
    def __init__(self):
        super().__init__("vad_transcriptor_action_server")

        self.declare_parameter("mic_topic", "/sancho_audio/microphone/mono")
        self.declare_parameter("vad_criterion", "intensity")
        self.declare_parameter("intensity_threshold", 900)
        self.declare_parameter("chunk_size", 0.5)
        self.declare_parameter("silence_patience_seconds", 1.5)

        self._action_server = ActionServer(
            self, ListenVoice, 'listen_voice',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback
        )

        self.stt_client = self.create_client(STT, 'sancho_hri/speech/stt')
        
        # Setup VAD Criterion
        criterion = self.get_parameter("vad_criterion").get_parameter_value().string_value
        threshold = self.get_parameter("intensity_threshold").get_parameter_value().integer_value
        if criterion == "intensity":
            self.chunk_attach_criterion = IntensityAttachCriterion(threshold)
        else:
            self.chunk_attach_criterion = SileroVADAttachCriterion()

        self.get_logger().info("VAD Transcriptor Action Server is ready.")

    def goal_callback(self, goal_request):
        self.get_logger().info("Received request to listen to voice.")
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        self.get_logger().info("Voice listening canceled.")
        return CancelResponse.ACCEPT

    async def execute_callback(self, goal_handle):
        self.get_logger().info(">>> START LISTENING <<<")
        
        # Initialize state for this action run
        audio_state = AudioState.NO_AUDIO
        audio_buffer = []
        check_audio_buffer = []
        previous_chunk = []
        start_listening_time = time.time()
        silence_timer = 0.0
        
        timeout = goal_handle.request.timeout_sec
        chunk_size = self.get_parameter("chunk_size").get_parameter_value().double_value
        patience = self.get_parameter("silence_patience_seconds").get_parameter_value().double_value
        mic_topic = self.get_parameter("mic_topic").get_parameter_value().string_value

        # Queue to pass audio from subscriber callback to this execution thread
        audio_queue = []
        
        def mic_callback(msg):
            new_audio = list([np.int16(x) for x in msg.chunk_mono])
            audio_queue.append((new_audio, msg.sample_rate))

        mic_sub = self.create_subscription(ChunkMono, mic_topic, mic_callback, 10)

        final_transcription = ""
        success = False

        try:
            while rclpy.ok() and not goal_handle.is_cancel_requested:
                # 1. Check Timeout (no one spoke)
                if audio_state == AudioState.NO_AUDIO and (time.time() - start_listening_time) > timeout:
                    self.get_logger().warn("Timeout: No voice detected.")
                    break

                # 2. Process audio queue
                while len(audio_queue) > 0:
                    new_audio, sample_rate = audio_queue.pop(0)
                    check_audio_buffer.extend(new_audio)

                    if len(check_audio_buffer) >= (chunk_size * sample_rate):
                        # VAD Logic
                        if self.chunk_attach_criterion.should_attach_chunk(check_audio_buffer, sample_rate):
                            silence_timer = 0.0
                            if audio_state == AudioState.NO_AUDIO:
                                audio_state = AudioState.SOME_AUDIO
                                audio_buffer.extend(previous_chunk)
                            audio_buffer.extend(check_audio_buffer)
                            
                        elif audio_state != AudioState.NO_AUDIO:
                            audio_buffer.extend(check_audio_buffer)
                            silence_timer += chunk_size
                            if silence_timer >= patience:
                                audio_state = AudioState.END_AUDIO
                                break # Stop processing audio, user is done

                        previous_chunk = check_audio_buffer
                        check_audio_buffer = []

                if audio_state == AudioState.END_AUDIO:
                    break
                
                # Sleep briefly to yield thread
                time.sleep(0.05)

            # 3. Handle STT if audio was captured
            if audio_state == AudioState.END_AUDIO and len(audio_buffer) > 0:
                self.get_logger().info("User finished speaking. Sending to STT...")
                if self.stt_client.wait_for_service(timeout_sec=1.0):
                    req = STT.Request()
                    req.audio = list(map(int, audio_buffer))
                    req.sample_rate = sample_rate
                    
                    # Async call to service, waiting for result
                    future = self.stt_client.call_async(req)
                    while rclpy.ok() and not future.done():
                        time.sleep(0.05)
                        
                    if future.result() is not None:
                        final_transcription = future.result().text
                        success = True
                        self.get_logger().info(f"Transcription: {final_transcription}")
                else:
                    self.get_logger().error("STT Service unavailable.")

        finally:
            # Clean up subscription
            self.destroy_subscription(mic_sub)

        # 4. Return Result to Behavior Tree
        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            self.get_logger().info("Action Canceled")
            return ListenVoice.Result()

        goal_handle.succeed()
        result = ListenVoice.Result()
        result.text = final_transcription
        result.success = success
        return result

def main(args=None):
    rclpy.init(args=args)
    node = VADTranscriptorActionServer()
    # Use MultiThreadedExecutor so the ActionServer and Subscriptions don't block each other
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(node)
    executor.spin()
    rclpy.shutdown()

if __name__ == '__main__':
    main()