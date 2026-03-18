import base64
import requests

from .stt_model import STTModel


class GoogleSTT(STTModel):
    def __init__(self, api_key: str):
        self.api_url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"

    def transcribe(self, audio: bytes, sample_rate: int) -> str:
        try:
            audio_base64 = base64.b64encode(audio).decode('utf-8')

            payload = {
                "config": {
                    "encoding": "LINEAR16",
                    "sampleRateHertz": sample_rate,
                    "languageCode": "es-ES"
                },
                "audio": {
                    "content": audio_base64
                }
            }

            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return ""

            alternatives = [
                alt
                for result in results
                for alt in result.get("alternatives", [])
                if "transcript" in alt and "confidence" in alt
            ]

            if not alternatives:
                return ""

            best = max(alternatives, key=lambda alt: alt["confidence"])
            return best["transcript"]

        except requests.RequestException as e:
            print(f"[GoogleSTT] Request failed: {e}")
        except (ValueError, KeyError) as e:
            print(f"[GoogleSTT] Failed to parse response: {e}")

        return ""
