from enum import Enum


class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class STT_MODELS(SmartStrEnum):
    WHISPER = "whisper"
    GOOGLE = "google"

class TTS_MODELS(SmartStrEnum):
    BARK = "bark"
    CSS10 = "css10"
    GOOGLE = "google"
    PIPER = "piper"
    TACOTRON2 = "tacotron2"
    XTTS = "xtts"
    YOUR_TTS = "your_tts"

class TTS_SPEAKERS:
    class BARK(SmartStrEnum):
        ES_SPEAKER_0 = "es_speaker_0"

    class CSS10(SmartStrEnum):
        pass

    class GOOGLE(SmartStrEnum):
        ES = "es"
        COM_MX = "com.mx"
        US = "us"
    
    class PIPER(SmartStrEnum):
        DAVEFX = "davefx"
        SHARVARD = "sharvard"
    
    class TACOTRON2(SmartStrEnum):
        pass

    class XTTS(SmartStrEnum):
        ALMA_MARIA = "Alma María"
        ANA_FLORENCE = "Ana Florence"
        LUIS_MORAY = "Luis Moray"
        VIKTOR_EKA = "Viktor Eka"
        MARCOS_RUDASKI = "Marcos Rudaski"
        FERRAN_SIMEN = "Ferran Simen"
        XAVIER_HAYASAKA = "Xavier Hayasaka"

    class YOUR_TTS(SmartStrEnum):
        FEMALE_EN_5 = "female-en-5"
        MALE_EN_2 = "male-en-2"

STT_NEEDS_API_KEY = {
    STT_MODELS.GOOGLE
}

TTS_NEEDS_API_KEY = {

}