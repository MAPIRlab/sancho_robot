import os
import wave
import numpy as np
import time

import rclpy
from rclpy.node import Node

from hri_msgs.msg import ChunkMono, ChunkStereo


class AudioNode(Node):

    def __init__(self, wav_path="sounds/sample.wav", chunk_size=1024):
        super().__init__('audio')

        self.publisher_stereo = self.create_publisher(ChunkStereo, 'hri_audio/microphone/stereo', 10)
        self.publisher_mono = self.create_publisher(ChunkMono, 'hri_audio/microphone/mono', 10)

        self.wav_path = os.path.join(os.path.dirname(__file__), wav_path)
        self.chunk_size = chunk_size

    def spin(self):
        first = True

        while rclpy.ok():
            try:
                wf = wave.open(self.wav_path, 'rb')

                sample_rate = wf.getframerate()
                num_channels = wf.getnchannels()

                self.get_logger().info(f"Reproducing {self.wav_path} with {sample_rate}hz and {num_channels} channels")

                while True:
                    chunk_stereo = ChunkStereo(sample_rate=sample_rate)
                    chunk_mono = ChunkMono(sample_rate=sample_rate)

                    data = wf.readframes(self.chunk_size)
                    data = np.frombuffer(data, dtype=np.int16)
                    if len(data) == 0:
                        break

                    audio_mix = np.ndarray.tolist(data)

                    if num_channels == 1:
                        chunk_mono.chunk_mono = audio_mix
                    elif num_channels >= 2:
                        chunk_stereo.chunk_left = audio_mix[::2]
                        chunk_stereo.chunk_right = audio_mix[1::2]

                        chunk_mono.chunk_mono = audio_mix[::2]

                        self.publisher_stereo.publish(chunk_stereo)

                    if first:
                        self.get_logger().info("First Audio Chunk published succesfully")
                        first = False

                    self.publisher_mono.publish(chunk_mono)

                    time.sleep(self.chunk_size / sample_rate)

                self.get_logger().info("Audio finished, waiting 5s before starting again...")
                time.sleep(5)
                wf.close()

            except Exception as e:
                self.get_logger().error(f"Error while reproducing audio: {e}")
                time.sleep(1)


def main(args=None):
    rclpy.init(args=args)

    audio = AudioNode()

    audio.spin()
    rclpy.shutdown()
