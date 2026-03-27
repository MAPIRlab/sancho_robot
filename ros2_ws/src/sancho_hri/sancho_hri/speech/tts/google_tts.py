import numpy as np

from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment

from .tts_model import TTSModel
from ..models import TTS_SPEAKERS


class GoogleTTS(TTSModel):

    def synthesize(self, text: str, speaker: str) -> tuple[list[int], str]:
        if not speaker:
            speaker = self.get_speakers()[0]
            
        mp3_fp = BytesIO()
        gTTS(text, lang="es", tld=speaker).write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        audio = AudioSegment.from_mp3(mp3_fp).set_channels(1)
        audio = np.array(audio.get_array_of_samples(), dtype=np.int16)

        max_val = np.max(np.abs(audio))
        if max_val > 0:
            scale = 32767 / max_val
            audio = (audio.astype(np.float32) * scale).clip(-32767, 32767).astype(np.int16)

        return audio.tolist(), speaker

    def get_sample_rate(self) -> int:
        return 24000
    
    def get_speakers(self) -> list[str]:
        return list(TTS_SPEAKERS.GOOGLE)