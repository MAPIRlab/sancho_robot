import os
import tempfile

import numpy as np
import rclpy
import soundfile as sf
from pyannote.audio import Pipeline
from rcl_interfaces.msg import ParameterDescriptor, ParameterType
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.parameter import ParameterType
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

from sancho_msgs.msg import AudioData, VADSegment


class VADDetectorNode(Node):
    """Voice Activity Detection (VAD) node for ROS2.

    This node processes incoming audio data to detect segments containing speech
    using the pyannote.audio library. It analyzes chunks of audio and publishes
    detected voice segments.

    The node:
    1. Receives raw audio data from a configurable topic
    2. Processes the audio using a Hugging Face VAD model
    3. Publishes detected speech segments with timestamps

    Features:
    - Dynamic parameter reconfiguration
    - Support for stereo audio processing
    - Configurable model selection from Hugging Face

    Parameters
    ----------
        sample_rate (int): Sampling rate of incoming audio (default: 48000)
        chunk_duration (float): Duration in seconds of each analysis chunk (default: 1.0)
        input_topic (str): ROS topic for raw audio input (default: "/audio/raw")
        output_topic (str): ROS topic for VAD segments output (default: "/audio/vad_segment")
        model_name (str): Hugging Face model for VAD (default: "pyannote/voice-activity-detection")
        hf_auth_token (str): Hugging Face authentication token (default: "None")

    Subscribes:
        AudioData: Raw audio data containing interleaved stereo samples

    Publishes:
        VADSegment: Detected voice activity segments with left/right audio channels and timing info

    """

    def __init__(self):
        super().__init__("vad_detector")

        # --- Declare parameters with descriptors ---
        self.declare_parameter(
            "sample_rate",
            48000,
            ParameterDescriptor(
                type=ParameterType.PARAMETER_INTEGER,
                description="Sampling rate of incoming audio",
            ),
        )
        self.declare_parameter(
            "chunk_duration",
            1.0,
            ParameterDescriptor(
                type=ParameterType.PARAMETER_DOUBLE,
                description="Duration of each analysis chunk (seconds)",
            ),
        )
        self.declare_parameter(
            "input_topic",
            "/audio/raw",
            ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="ROS topic for raw audio input",
            ),
        )
        self.declare_parameter(
            "output_topic",
            "/audio/vad_segment",
            ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="ROS topic for VAD segments output",
            ),
        )
        self.declare_parameter(
            "model_name",
            "pyannote/voice-activity-detection",
            ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="Hugging Face model for VAD",
            ),
        )
        self.declare_parameter(
            "hf_auth_token",
            "None",
            ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description="Hugging Face authentication token",
            ),
        )

        # --- Initialize parameters ---
        self._read_parameters()

        # --- Parameter change callback ---
        self.add_on_set_parameters_callback(self._on_parameter_change)

        # --- QoS settings ---
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        callback_group = ReentrantCallbackGroup()

        # --- Subscribers & Publishers ---
        self.subscription = self.create_subscription(
            AudioData,
            self.input_topic,
            self.audio_callback,
            qos_profile=qos,
            callback_group=callback_group,
        )
        self.publisher = self.create_publisher(
            VADSegment, self.output_topic, qos_profile=qos
        )

        # --- Instantiate VAD pipeline ---
        self.pipeline = Pipeline.from_pretrained(
            self.model_name,
            use_auth_token=self.hf_auth_token if self.hf_auth_token != "None" else None,
        )

        self.get_logger().info("VADDetectorNode initialized")

    def _read_parameters(self):
        self.sample_rate = (
            self.get_parameter("sample_rate").get_parameter_value().integer_value
        )
        self.chunk_duration = (
            self.get_parameter("chunk_duration").get_parameter_value().double_value
        )
        self.input_topic = (
            self.get_parameter("input_topic").get_parameter_value().string_value
        )
        self.output_topic = (
            self.get_parameter("output_topic").get_parameter_value().string_value
        )
        self.model_name = (
            self.get_parameter("model_name").get_parameter_value().string_value
        )
        self.hf_auth_token = (
            self.get_parameter("hf_auth_token").get_parameter_value().string_value
        )
        self.chunk_samples = int(self.sample_rate * self.chunk_duration)
        # Buffers
        self.buffer_left = []
        self.buffer_right = []

    def _on_parameter_change(self, params):  # type: ignore
        """Handle dynamic parameter updates."""
        for param in params:
            if param.name in ["sample_rate", "chunk_duration"]:
                self.get_logger().info(
                    f"Parameter '{param.name}' changed, reconfiguring... "
                )
        # Re-read and apply
        self._read_parameters()
        # Recreate pipeline if model parameters changed
        for param in params:
            if param.name in ["model_name", "hf_auth_token"]:
                self.pipeline = Pipeline.from_pretrained(
                    self.model_name, use_auth_token=self.hf_auth_token
                )
                self.get_logger().info("Pipeline reloaded with new model settings")
        return rclpy.node.SetParametersResult(successful=True)

    def audio_callback(self, msg: AudioData):
        # Separate interleaved stereo samples into two channels
        samples = np.array(msg.data, dtype=np.int16)
        self.buffer_left.extend(samples[0::2].tolist())
        self.buffer_right.extend(samples[1::2].tolist())

        # Process full chunks
        while len(self.buffer_left) >= self.chunk_samples:
            left_chunk = np.array(
                self.buffer_left[: self.chunk_samples], dtype=np.int16
            )
            right_chunk = np.array(
                self.buffer_right[: self.chunk_samples], dtype=np.int16
            )
            del self.buffer_left[: self.chunk_samples]
            del self.buffer_right[: self.chunk_samples]

            # Write a temporary WAV file for detection
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                sf.write(tf.name, left_chunk.astype(np.float32), self.sample_rate)
                temp_path = tf.name

            # Run VAD
            vad_result = self.pipeline(temp_path)
            os.remove(temp_path)

            # Publish detected segments
            for segment in vad_result.get_timeline().support():
                start_idx = int(segment.start * self.sample_rate)
                end_idx = int(segment.end * self.sample_rate)
                start_idx = max(0, min(start_idx, len(left_chunk)))
                end_idx = max(0, min(end_idx, len(left_chunk)))

                vad_msg = VADSegment(
                    left_channel=left_chunk[start_idx:end_idx].tolist(),
                    right_channel=right_chunk[start_idx:end_idx].tolist(),
                    start_time=segment.start,
                    end_time=segment.end,
                    sample_rate=self.sample_rate,
                )
                self.publisher.publish(vad_msg)
                self.get_logger().info(
                    f"Published VAD segment {segment.start:.2f}-{segment.end:.2f}s"
                )

    def destroy_node(self):
        self.get_logger().info("Shutting down VADDetectorNode")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VADDetectorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
