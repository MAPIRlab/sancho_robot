from enum import Enum

class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class COMMANDS(SmartStrEnum):
    DELETE_USER = "DELETE_USER",
    RENAME_USER = "RENAME_USER",
    TAKE_PICTURE = "TAKE_PICTURE"
    
    UNKNOWN = "UNKNOWN"

class COMMAND_RESUITS(SmartStrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    MISSING_ARGUMENT = "MISSING_ARGUMENT"