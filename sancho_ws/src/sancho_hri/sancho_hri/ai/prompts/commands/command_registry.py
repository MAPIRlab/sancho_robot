import os
import json

class CommandRegistry:
    _commands = None

    @classmethod
    def get_commands(cls):
        if cls._commands is None:
            current_dir = os.path.dirname(__file__)
            path = os.path.join(current_dir, 'commands.json')
            with open(path, 'r', encoding='utf-8') as f:
                cls._commands = json.load(f)
        return cls._commands
