import os
from .sound import load

activation_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds/activation_sound.wav")
time_out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds/time_out_sound.wav")

ACTIVATION_SOUND = load(activation_path)
TIME_OUT_SOUND = load(time_out_path)
