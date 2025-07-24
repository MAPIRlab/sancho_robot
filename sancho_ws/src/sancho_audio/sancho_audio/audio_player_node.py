import os

import rclpy
from playsound import PlaysoundException, playsound
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from sancho_msgs.action import PlayAudio


class AudioPlayer(LifecycleNode):
    """Audio Player Node for ROS 2 using lifecycle management.

    This node provides an action server to play audio files in WAV or MP3 formats.
    It follows the managed lifecycle pattern, allowing for proper initialization,
    activation, deactivation and cleanup.

    The node exposes a 'play_audio' action that accepts a file path and plays
    the audio using the playsound library. The action server is only available
    when the node is in the active state.

    Usage:
        1. Configure the node to initialize internal structures
        2. Activate the node to start the action server
        3. Send play_audio actions with valid audio file paths
        4. Deactivate when done to clean up resources

    Dependencies:
        - ROS 2 lifecycle
        - playsound library for audio playback
        - PlayAudio action type
    """

    def __init__(self):
        super().__init__("audio_player_lifecycle")

        # Action server will be created on activation
        self._action_server = None
        self._current_task = None

        self.get_logger().info("AudioPlayerLifecycle creado, esperando configuración.")

    def on_configure(self, state) -> TransitionCallbackReturn:
        """Inicializa el ActionServer pero no lo activa aún."""
        self.get_logger().info("Configuring: creating action server...")
        self.get_logger().info("Configurado correctamente.")
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
        # Cancel any playing audio
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
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
        if not goal_request.filename.endswith((".wav", ".mp3")):
            self.get_logger().warn(f"Unsupported file format: {goal_request.filename}")
            return GoalResponse.REJECT

        self.get_logger().info(f"Received request to play: {goal_request.filename}")
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle) -> CancelResponse:
        self.get_logger().info("Cancel requested")
        # TODO: implementar cancelación en el futuro
        return CancelResponse.ACCEPT

    def _play_audio(self, goal_handle):
        # TODO: implementar cancelación en el futuro
        filename = goal_handle.request.filename
        result = PlayAudio.Result()
        try:
            self.get_logger().info(f"Reproduciendo: {filename}")
            playsound(filename)
        except PlaysoundException as e:
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

    def execute_callback(self, goal_handle) -> PlayAudio.Result:
        # Lanza la reproducción y espera a que termine (o se cancele)
        return self._play_audio(goal_handle)


def main(args=None):
    rclpy.init(args=args)
    node = AudioPlayer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
