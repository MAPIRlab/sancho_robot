import re
import json

from abc import ABC, abstractmethod


class Prompt(ABC):

    @abstractmethod
    def get_prompt_system(self):
        pass

    @abstractmethod
    def get_user_prompt(self):
        pass

    @abstractmethod
    def get_parameters(self):
        pass


    @staticmethod
    def try_json_loads(text):
        try:
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def extract_json_from_code_block(text):
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return None
