import os
import re
import subprocess
import pyaudio
import numpy as np

import rclpy
from rclpy.node import Node

from hri_msgs.msg import ChunkMono, ChunkStereo


class MicrophoneCapturerNode(Node):
    def __init__(self):
        super().__init__("microphone_capturer")
        
        self.declare_parameter("device_name", "xvf3800")
        self.declare_parameter("chunk_size", 1024)

        self.publisher_stereo = self.create_publisher(ChunkStereo, "sancho_audio/microphone/stereo", 10)
        self.publisher_mono = self.create_publisher(ChunkMono, "sancho_audio/microphone/mono", 10)


class MicrophoneCapturer:
    def __init__(self):
        self.node = MicrophoneCapturerNode()
        self.p = pyaudio.PyAudio()

        self.device_name = self.node.get_parameter("device_name").get_parameter_value().string_value
        self.chunk_size = int(self.node.get_parameter("chunk_size").get_parameter_value().integer_value or 1024)

        if self.device_name.lower() == "xvf3800":
            device, sr, ch = self.get_device_xvf3800()
        else:
            device = self.get_device_by_name(self.device_name)
            if not device:
                raise Exception(f"Microphone with name '{self.device_name}' not found.")

            sr = int(device.get("defaultSampleRate", 16000))
            ch = int(device.get("maxInputChannels", 1))

        self.device_index = device["index"]
        self.sample_rate = sr
        self.num_channels = ch
        
        self.stream = self.setup_microphone(self.device_index, self.sample_rate, self.num_channels, self.chunk_size)

        self.node.get_logger().info(f"Mic='{device['name']}' (index={self.device_index}) sr={self.sample_rate}Hz ch={self.num_channels} chunk={self.chunk_size}")

    def spin(self):
        first = True

        while rclpy.ok():
            try:      
                chunk_stereo = ChunkStereo(sample_rate=self.sample_rate)
                chunk_mono = ChunkMono(sample_rate=self.sample_rate)
                
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                data = np.frombuffer(data, dtype=np.int16)

                audio_mix = np.ndarray.tolist(data)

                if self.num_channels == 1:
                    chunk_mono.chunk_mono = audio_mix

                elif self.num_channels >= 2:
                    chunk_stereo.chunk_left = audio_mix[::2]
                    chunk_stereo.chunk_right  = audio_mix[1::2]

                    chunk_mono.chunk_mono = audio_mix[::2]

                    self.node.publisher_stereo.publish(chunk_stereo)

                if first:
                    self.node.get_logger().info("First Audio Chunk published succesfully")
                    first = False
                
                self.node.publisher_mono.publish(chunk_mono)
            except Exception as e:
                 self.node.get_logger().info(f">> Microphone Publisher Error: {e}")

    def get_device_by_name(self, name_substr: str):
        target = None
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                if name_substr.lower() in dev["name"].lower():
                    d = dict(dev); d["index"] = i
                    target = d
                    break
        return target

    def get_device_xvf3800(self):
        try:
            out = subprocess.check_output(["pactl", "list", "sources", "short"], text=True)
            src_name = None
            for ln in out.strip().splitlines():
                parts = ln.split("\t")
                if len(parts) >= 2 and re.search(r"(respeaker|xvf3800|seeed|4-mic)", parts[1], re.I):
                    src_name = parts[1]; break
            if src_name:
                os.environ["PULSE_SOURCE"] = src_name
            else:
                self.node.get_logger().warn("XVF3800: Pulse source not found (select it as default input in your system).")
        except Exception as e:
            self.node.get_logger().warn(f"XVF3800: pactl error: {e}")

        pulse_dev = None
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0 and dev["name"].lower() == "pulse":
                pulse_dev = dict(dev); pulse_dev["index"] = i; break
        if not pulse_dev:
            raise Exception("XVF3800: no 'pulse' input device found in PyAudio.")

        forced_sr = 16000
        forced_ch = min(2, int(pulse_dev.get("maxInputChannels", 2)) or 2)
        return pulse_dev, forced_sr, forced_ch

    def setup_microphone(self, device_index, sample_rate, num_channels, chunk_size):
        return self.p.open(format=pyaudio.paInt16,
                           channels=num_channels,
                           rate=sample_rate,
                           input=True,
                           frames_per_buffer=chunk_size,
                           input_device_index=device_index)



def main(args=None):
    rclpy.init(args=args)

    microphone_capturer = MicrophoneCapturer()

    microphone_capturer.spin()
    rclpy.shutdown()