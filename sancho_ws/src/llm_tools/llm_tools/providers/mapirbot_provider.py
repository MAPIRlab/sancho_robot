import requests
import json
from .api_provider import APIProvider

class MapirbotProvider(APIProvider):
    def __init__(self, api_url="https://olympics-housewives-however-different.trycloudflare.com/ask"):
        self.api_url = api_url

    def prompt(self, model, prompt_system, messages_json, user_input, parameters_json):
        payload = {
            "query": user_input,
            "thread_id": "Mapirbot_thread"
        }
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(self.api_url, data=json.dumps(payload), headers=headers)

        if response.status_code == 200:
            print(f"[INFO] Response from Mapirbot: {response.json()}")
            return json.dumps(response.json(), indent=2), model
        else:
            print(f"[ERROR] Error from Mapirbot: {response.status_code}")
            return "Error from Mapirbot", model

    def embedding(self, model, user_input):
        pass

    def get_active_models(self):
        return ["mapirbot"]