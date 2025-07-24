import json

from enum import Enum
from abc import ABC, abstractmethod


##### SERVER MESSAGES #####
class JSONMessage(ABC):
    @abstractmethod
    def to_dict(self) -> dict:
        pass

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
class Message(JSONMessage):
    def __init__(self, data):
        self.data = data
    
    def to_dict(self):
        return {
            "type": MessageType.MESSAGE,
            "data": self.data
        }
    
class TopicMessage(JSONMessage):
    def __init__(self, topic, name, value):
        self.topic = topic
        self.name = name
        self.value = value

    def to_dict(self):
        return {
            "type": MessageType.TOPIC,
            "data": {
                "topic": self.topic,
                "name": self.name,
                "value": self.value
            }
        }


##### TYPES #####
class MessageType(str, Enum):
    MESSAGE = "MESSAGE"
    TOPIC = "TOPIC"


MESSAGE_OBJECT = {
    MessageType.MESSAGE: Message,
    MessageType.TOPIC: TopicMessage
}


##### PARSER #####
def parse_message(msg):
    try:
        msg = json.loads(msg)
        return msg.get("type"), msg.get("data")
    except json.JSONDecodeError:
        print("Error: mensaje JSON malformado")
        return None, None