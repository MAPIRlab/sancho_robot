import torch
import numpy as np

from rclpy.node import Node
from scipy.signal import resample_poly


class IntensityAttachCriterion(Node):
    
    def __init__(self, intensity_threshold):
        self.intensity_threshold = intensity_threshold

    def should_attach_chunk(self, chunk, _):
        avg_intensity = self.audio_average_intensity(chunk)

        return avg_intensity >= self.intensity_threshold
    
    def audio_average_intensity(self, chunk):
        average_intensity = np.mean(np.abs(chunk))
        if average_intensity < 0:
            average_intensity = 32767
            
        return average_intensity
