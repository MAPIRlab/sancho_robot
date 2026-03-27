import os
import time

import rclpy
import pygame
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.executors import MultiThreadedExecutor

from sancho_interfaces.action import PlayAudio

from .utils.sound import load

class AudioPlayer(LifecycleNode):
    """Audio Player Node for ROS 2 using lifecycle management.

    This node provides an action server to play audio files using pygame.
    It supports clean cancellation and non-blocking playback.
    """

    def __init__(self):
        super().__init__("audio_player_lifecycle")

        # Action server will be created on activation
        self._action_server = None
        self._current_task = None

        self.get_logger().info("AudioPlayerLifecycle creado, esperando configuración.")

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("AudioPlayer CONFIGURED")
        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        # Create action server
        self._action_server = ActionServer(
            self,
            PlayAudio,
            "play_audio",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
        )

        self.get_logger().info("AudioPlayer ACTIVATED: starting action server")
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        # Stop any audio playing
        if pygame.mixer.get_init() and pygame.mixer.get_busy():
            pygame.mixer.stop()
            
        # Destroy action server
        if self._action_server:
            self._action_server.destroy()
            self._action_server = None

        self.get_logger().info("AudioPlayer DEACTIVATED: shutting down")
        return super().on_deactivate(state)

    def goal_callback(self, goal_request) -> GoalResponse:
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

    def cancel_callback(self, goal_handle) -> CancelResponse:
        self.get_logger().info("Cancel requested")
        return CancelResponse.ACCEPT

    def execute_callback(self, goal_handle) -> PlayAudio.Result:
        filename = goal_handle.request.filename
        result = PlayAudio.Result()
        
        try:
            self.get_logger().info(f"Reproduciendo con pygame: {filename}")
            
            sound = load(filename)
            channel = sound.play()
            
            # Wait until it is finished, checking if action is cancelled
            while channel and channel.get_busy():
                if goal_handle.is_cancel_requested:
                    self.get_logger().info("Deteniendo el audio por petición de cancelación...")
                    channel.stop()
                    goal_handle.canceled()
                    result.success = False
                    result.message = "Reproducción cancelada"
                    return result
                
                time.sleep(0.05)
                
        except Exception as e:
            self.get_logger().error(f"Error al reproducir audio: {e}")
            result.success = False
            result.message = str(e)
            goal_handle.abort()
            return result

        self.get_logger().info("Reproducción finalizada.")
        result.success = True
        result.message = "Reproducción completada correctamente"
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
