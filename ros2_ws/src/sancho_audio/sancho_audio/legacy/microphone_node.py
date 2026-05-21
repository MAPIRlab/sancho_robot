import os
import re
import ctypes
from contextlib import contextmanager
import pyaudio
import numpy as np

import rclpy
from rclpy.node import Node

from sancho_interfaces.msg import ChunkMono, ChunkStereo

# --- ALSA Error Suppression ---
ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

@contextmanager
def noalsaerr():
    try:
        asound = ctypes.cdll.LoadLibrary('libasound.so.2')
        asound.snd_lib_error_set_handler(c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except Exception:
        yield

class MicrophoneCapturerNode(Node):
    def __init__(self):
        super().__init__("microphone_capturer")
        
        self.declare_parameter("device_name", "xvf3800")
        self.declare_parameter("chunk_size", 1024)

        self.device_name_param = self.get_parameter("device_name").get_parameter_value().string_value
        self.chunk_size = self.get_parameter("chunk_size").get_parameter_value().integer_value

        self.publisher_stereo = self.create_publisher(ChunkStereo, "sancho_audio/microphone/stereo", 10)
        self.publisher_mono = self.create_publisher(ChunkMono, "sancho_audio/microphone/mono", 10)

        with noalsaerr():
            self.p = pyaudio.PyAudio()

        device = self.get_device_by_name(self.device_name_param)
        if not device:
            self.get_logger().error(f"Microphone with name '{self.device_name_param}' not found.")
            raise RuntimeError(f"Microphone with name '{self.device_name_param}' not found.")

        self.device_index = device["index"]
        self.sample_rate = int(device.get("defaultSampleRate", 16000))
        self.num_channels = int(device.get("maxInputChannels", 1))
        
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.num_channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=self.device_index
            )
        except Exception as e:
            self.get_logger().error(f"Failed to open microphone stream: {e}")
            raise e

        self.get_logger().info(f"Mic='{device['name']}' (index={self.device_index}) sr={self.sample_rate}Hz ch={self.num_channels} chunk={self.chunk_size}")

        self.chunk_count = 0
        self.first_chunk = True
        
        # Timer-based capture
        timer_period = self.chunk_size / self.sample_rate
        self.timer = self.create_timer(timer_period, self.timer_callback)

    def get_device_by_name(self, name_substr: str):
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                if name_substr.lower() in dev["name"].lower():
                    d = dict(dev)
                    d["index"] = i
                    return d
        return None

    def timer_callback(self):
        try:
            # Read audio data
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            audio_list = audio_data.tolist()

            chunk_mono = ChunkMono(sample_rate=self.sample_rate)
            
            if self.num_channels == 1:
                chunk_mono.chunk_mono = audio_list
            elif self.num_channels >= 2:
                # Interleaved: L, R, L, R...
                # We take left channel for mono
                chunk_mono.chunk_mono = audio_list[::self.num_channels]
                
                if self.num_channels == 2:
                    chunk_stereo = ChunkStereo(sample_rate=self.sample_rate)
                    chunk_stereo.chunk_left = audio_list[::2]
                    chunk_stereo.chunk_right = audio_list[1::2]
                    self.publisher_stereo.publish(chunk_stereo)

            self.publisher_mono.publish(chunk_mono)

            if self.first_chunk:
                self.get_logger().info("First Audio Chunk published successfully")
                self.first_chunk = False
            
            self.chunk_count += 1
            if self.chunk_count % 100 == 0:
                self.get_logger().debug(f"Published {self.chunk_count} chunks")

        except Exception as e:
            self.get_logger().error(f"Microphone Capture Error: {e}")

    def destroy_node(self):
        if hasattr(self, 'stream'):
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if hasattr(self, 'p'):
            try:
                self.p.terminate()
            except Exception:
                pass
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    try:
        node = MicrophoneCapturerNode()
        rclpy.spin(node)
    except Exception as e:
        # Using print because logger might not be available if init failed
        print(f"Node startup failed: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()