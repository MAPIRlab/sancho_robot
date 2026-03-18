import json

from enum import Enum
from abc import ABC, abstractmethod


##### CLIENT MESSAGES #####
class PromptMessage():
    def __init__(self, msg):
        self.id = msg["id"]
        self.chat_id = msg["chatId"]
        self.want_tts = msg["wantTts"]
        self.value = msg["value"]

class AudioPromptMessage():
    def __init__(self, msg):
        self.id = msg["id"]
        self.chat_id = msg["chatId"]
        self.want_tts = msg["wantTts"]
        self.audio = msg["audio"]
        self.sample_rate = msg["sampleRate"]

class TranscriptionRequestMessage():
    def __init__(self, msg):
        self.id = msg["id"]
        self.audio = msg["audio"]
        self.sample_rate = msg["sampleRate"]

##### SERVER MESSAGES #####
class JSONMessage(ABC):
    @abstractmethod
    def to_dict(self) -> dict:
        pass

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class ResponseMessage(JSONMessage):
    def __init__(self, id, value, method, intent, arguments, provider, model):
        self.id = id
        self.value = value
        self.method = method
        self.intent = intent
        self.arguments = arguments
        self.provider = provider
        self.model = model
    
    def to_dict(self):
        return {
            "type": MessageType.RESPONSE,
            "data": {
                "id": self.id,
                "method": self.method,
                "intent": self.intent,
                "arguments": self.arguments,
                "provider": self.provider,
                "model": self.model,
                "value": self.value
            }
        }


class FaceprintEventMessage(JSONMessage):
    class Event(str, Enum):
        CREATE = "CREATE"
        UPDATE = "UPDATE"
        DELETE = "DELETE"

    def __init__(self, event, id):
        self.event = event
        self.id = id
    
    def to_dict(self):
        return {
            "type": MessageType.FACEPRINT_EVENT,
            "data": {
                "event": self.event,
                "id": self.id
            }
        }

class PromptTranscriptionMessage(JSONMessage):
    def __init__(self, id, value, model):
        self.id = id
        self.value = value
        self.model = model
    
    def to_dict(self):
        return {
            "type": MessageType.PROMPT_TRANSCRIPTION,
            "data": {
                "id": self.id,
                "model": self.model,
                "value": self.value
            }
        }

class AudioResponseMessage(JSONMessage):
    def __init__(self, id, audio, sample_rate, model, speaker):
        self.id = id
        self.audio = list(audio)
        self.sample_rate = sample_rate
        self.model = model
        self.speaker = speaker
        
    def to_dict(self):
        return {
            "type": MessageType.AUDIO_RESPONSE,
            "data": {
                "id": self.id,
                "model": self.model,
                "speaker": self.speaker,
                "audio": self.audio,
                "sampleRate": self.sample_rate
            }
        }

##### TYPES #####
class MessageType(str, Enum):
    PROMPT = "PROMPT" # Client -> Server
    AUDIO_PROMPT = "AUDIO_PROMPT" # Client -> Server
    TRANSCRIPTION_REQUEST = "TRANSCRIPTION_REQUEST" # Client -> Server

    RESPONSE = "RESPONSE" # Server -> Client
    FACEPRINT_EVENT = "FACEPRINT_EVENT" # Server -> Client
    PROMPT_TRANSCRIPTION = "PROMPT_TRANSCRIPTION" # Server -> Client
    AUDIO_RESPONSE = "AUDIO_RESPONSE" # Server -> Client
    
MESSAGE_OBJECT = {
    MessageType.PROMPT: PromptMessage,
    MessageType.AUDIO_PROMPT: AudioPromptMessage,
    MessageType.TRANSCRIPTION_REQUEST: TranscriptionRequestMessage,

    MessageType.RESPONSE: ResponseMessage,
    MessageType.FACEPRINT_EVENT: FaceprintEventMessage,
    MessageType.PROMPT_TRANSCRIPTION: PromptTranscriptionMessage,
    MessageType.AUDIO_RESPONSE: AudioResponseMessage
}


##### PARSER #####
def parse_message(msg):
    try:
        msg = json.loads(msg)
        return msg.get("type"), msg.get("data")
    except json.JSONDecodeError:
        print("Error: mensaje JSON malformado")
        return None, None
