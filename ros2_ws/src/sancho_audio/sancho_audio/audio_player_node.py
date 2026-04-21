import os
import time

import rclpy
import pygame
import sounddevice as sd
import numpy as np
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup

from sancho_interfaces.action import PlayAudio, PlayTTS
from sancho_interfaces.srv import TTS

from .utils.sound import load

class AudioPlayer(LifecycleNode):
    """Audio Player Node for ROS 2 using lifecycle management.

    This node provides action servers to play audio files using pygame 
    and to synthesize/play text using a TTS service and sounddevice.
    It supports clean cancellation and non-blocking playback.
    """

    def __init__(self):
        super().__init__("audio_player_lifecycle")

        # Track active state for Python lifecycle nodes
        self._is_active = False 

        # Callback groups to prevent deadlocks when calling services from within actions
        self.action_cb_group = ReentrantCallbackGroup()
        self.service_cb_group = MutuallyExclusiveCallbackGroup()

        # Action servers and clients will be created on configuration
        self._play_action_server = None
        self._say_action_server = None
        self._tts_client = None

        self.get_logger().info("AudioPlayerLifecycle created, waiting for configuration.")

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        # Create action server for playing audio files
        self._play_action_server = ActionServer(
            self,
            PlayAudio,
            "play_audio",
            execute_callback=self.play_execute_callback,
            goal_callback=self.play_goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.action_cb_group
        )

        # Create action server for TTS generation and playback
        self._say_action_server = ActionServer(
            self,
            PlayTTS,
            "play_tts",
            execute_callback=self.say_execute_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.action_cb_group
        )

        # Create client for the TTS service
        self._tts_client = self.create_client(
            TTS, 
            'sancho_hri/speech/tts', 
            callback_group=self.service_cb_group
        )

        self.get_logger().info("AudioPlayer CONFIGURED: Action servers and clients created.")
        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self._is_active = True
        self.get_logger().info("AudioPlayer ACTIVATED: Ready to process goals.")
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self._is_active = False
        
        # Stop any audio playing via pygame
        if pygame.mixer.get_init() and pygame.mixer.get_busy():
            pygame.mixer.stop()
            
        # Stop any audio playing via sounddevice
        sd.stop()

        self.get_logger().info("AudioPlayer DEACTIVATED: Hardware playback halted.")
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        # Destroy action servers and clients
        if self._play_action_server:
            self._play_action_server.destroy()
            self._play_action_server = None
            
        if self._say_action_server:
            self._say_action_server.destroy()
            self._say_action_server = None
            
        if self._tts_client:
            self.destroy_client(self._tts_client)
            self._tts_client = None

        self.get_logger().info("AudioPlayer CLEANED UP: Entities destroyed.")
        return super().on_cleanup(state)

    # ==========================================
    # GENERAL CALLBACKS
    # ==========================================
    
    def cancel_callback(self, goal_handle) -> CancelResponse:
        self.get_logger().info("Cancel requested")
        return CancelResponse.ACCEPT


    # ==========================================
    # ACTION: PLAY TTS
    # ==========================================

    def say_execute_callback(self, goal_handle):
        # Prevent execution if node is not Active
        if not self._is_active:
            self.get_logger().warn("Rejecting TTS goal: Node is not ACTIVE.")
            goal_handle.abort()
            return PlayTTS.Result()

        text = goal_handle.request.text
        result = PlayTTS.Result()
        
        self.get_logger().info(f"Received request to speak: '{text}'")

        # 1. Call TTS service asynchronously
        if not self._tts_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().error("TTS Service is not available.")
            goal_handle.abort()
            result.success = False
            return result

        req = TTS.Request()
        req.text = text

        future = self._tts_client.call_async(req)
        
        # Wait for the response without blocking the executor
        while not future.done():
            if goal_handle.is_cancel_requested:
                self.get_logger().info("Canceling TTS generation request.")
                goal_handle.canceled()
                result.success = False
                return result
            time.sleep(0.05)

        response = future.result()

        if not response or not response.success:
            self.get_logger().error("Failed to generate TTS audio.")
            goal_handle.abort()
            result.success = False
            return result

        # 2. Play the audio array with sounddevice
        try:
            audio_array = np.array(response.audio, dtype=np.int16)
            sample_rate = response.sample_rate
            duration = len(audio_array) / sample_rate
            
            self.get_logger().info(f"Playing TTS audio ({duration:.2f} seconds)...")
            sd.play(audio_array, samplerate=sample_rate)
            start_time = time.time()
            
            # 3. Keep the Action RUNNING while playing
            while (time.time() - start_time) < duration:
                if goal_handle.is_cancel_requested:
                    self.get_logger().info("Silencing audio playback due to cancel request.")
                    sd.stop()
                    goal_handle.canceled()
                    result.success = False
                    return result
                time.sleep(0.05)
                
        except Exception as e:
            self.get_logger().error(f"Error playing TTS audio: {e}")
            goal_handle.abort()
            result.success = False
            return result

        self.get_logger().info("TTS playback finished.")
        goal_handle.succeed()
        result.success = True
        return result


    # ==========================================
    # ACTION: PLAY AUDIO (Files)
    # ==========================================

    def play_goal_callback(self, goal_request) -> GoalResponse:
        # Prevent accepting goals if node is not Active
        if not self._is_active: 
            self.get_logger().warn("Rejecting audio goal: Node is not ACTIVE.")
            return GoalResponse.REJECT

        if not goal_request.filename:
            self.get_logger().warn("Received empty filename in goal")
            return GoalResponse.REJECT
        if not os.path.isfile(goal_request.filename):
            self.get_logger().warn(f"File does not exist: {goal_request.filename}")
            return GoalResponse.REJECT
        if not goal_request.filename.endswith((".wav", ".mp3", ".ogg")):
            self.get_logger().warn(f"Unsupported file format: {goal_request.filename}")
            return GoalResponse.REJECT

        self.get_logger().info(f"Received request to play: {goal_request.filename}")
        return GoalResponse.ACCEPT

    def play_execute_callback(self, goal_handle) -> PlayAudio.Result:
        filename = goal_handle.request.filename
        result = PlayAudio.Result()
        
        try:
            self.get_logger().info(f"Playing with pygame: {filename}")
            
            sound = load(filename)
            channel = sound.play()
            
            # Wait until it is finished, checking if action is cancelled
            while channel and channel.get_busy():
                if goal_handle.is_cancel_requested:
                    self.get_logger().info("Stopping audio due to cancel request...")
                    channel.stop()
                    goal_handle.canceled()
                    result.success = False
                    result.message = "Playback canceled"
                    return result
                
                time.sleep(0.05)
                
        except Exception as e:
            self.get_logger().error(f"Error playing audio file: {e}")
            result.success = False
            result.message = str(e)
            goal_handle.abort()
            return result

        self.get_logger().info("Playback finished.")
        result.success = True
        result.message = "Playback completed successfully"
        goal_handle.succeed()
        return result


def main(args=None):
    rclpy.init(args=args)
    node = AudioPlayer()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()