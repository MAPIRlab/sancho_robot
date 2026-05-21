import pyttsx3
import numpy as np
import tempfile
import os
from pydub import AudioSegment
from .tts_model import TTSModel

class Pyttsx3TTS(TTSModel):
    def __init__(self, **kwargs):
        self.engine = pyttsx3.init()
        # Set Spanish as default if available
        voices = self.engine.getProperty('voices')
        for voice in voices:
            if "es" in voice.languages or "spanish" in voice.name.lower():
                self.engine.setProperty('voice', voice.id)
                break

    def synthesize(self, text: str, speaker: str) -> tuple[list[int], str]:
        # Create a temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            self.engine.save_to_file(text, tmp_path)
            self.engine.runAndWait()
            
            # Load with pydub to ensure format
            audio = AudioSegment.from_file(tmp_path).set_channels(1).set_frame_rate(22050)
            audio_data = np.array(audio.get_array_of_samples(), dtype=np.int16)
            
            return audio_data.tolist(), "default"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def get_sample_rate(self) -> int:
        return 22050
    
    def get_speakers(self) -> list[str]:
        return ["default"]
