import torch
import numpy as np

from rclpy.node import Node
from scipy.signal import resample_poly


class SileroVAD(Node):
    
    VAD_SAMPLE_RATE = 16000

    def __init__(self):
        model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True)
        (get_speech_ts, _, _, _, _) = utils

        self.model = model
        self.get_speech_ts = get_speech_ts

    def has_human_voice(self, audio, sample_rate):
        audio_np = np.array(audio, dtype=np.float32) / 32768.0

        audio_resampled_np = resample_poly(audio_np, self.VAD_SAMPLE_RATE, sample_rate)
        audio_resampled = torch.from_numpy(audio_resampled_np)

        segments = self.get_speech_ts(audio_resampled, self.model, sampling_rate=self.VAD_SAMPLE_RATE)
        
        return bool(segments)

