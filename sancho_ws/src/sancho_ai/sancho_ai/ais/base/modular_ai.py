import json

from datetime import datetime
from abc import ABC

from ..intent_classifiers import IntentClassifier
from ..intent_executors import IntentExecutor
from ..response_generators import ResponseGenerator

from ...prompts.commands.commands import COMMANDS
from ...engines import HRIEngine


class ModularAI(ABC):
    def __init__(self, hri_engine: HRIEngine, classifier: IntentClassifier, executor: IntentExecutor, response_generator: ResponseGenerator):
        self.hri_engine = hri_engine
        self.classifier = classifier
        self.executor = executor
        self.response_generator = response_generator

    def on_message(self, user_input: str, chat_history: list, user_id: str, user_name: str, user_memory: str):
        history_classify = self._get_history_for_classify(chat_history) 
        intent, arguments, _, _ = self.classifier.classify(user_input, history_classify)
        
        if intent != COMMANDS.UNKNOWN:
            details, status, data = self.executor.execute(intent, arguments)

            response, emotion, provider_used, model_used = self.response_generator.generate_response(
                details, status, intent, arguments, user_input
            )

        else:
            data = {}

            robot_context = self._build_robot_context()
            history_conversation = self._get_history_for_conversation(chat_history)
            response, emotion, provider_used, model_used = self.response_generator.continue_conversation(
                user_input, robot_context, history_conversation, user_id, user_name, user_memory
            )

        value = {
            "text": response,
            "emotion": emotion,
            "data": data
        }

        return value, intent, arguments, provider_used, model_used

    def _get_history_for_classify(self, chat_history): # History with just role and content
        return [{k: m[k] for k in ["role", "content"] if k in m} for m in chat_history]
    
    def _get_history_for_conversation(self, chat_history): # Role and content with [id:name] content
        return [{k: (f"[{m['id']}|{m['name']}] {m[k]}" if k == "content" and m["role"] == "user" else m[k]) 
                 for k in ["role", "content"] if k in m} for m in chat_history]
    
    def _build_robot_context(self):
        actual_people_json = self.hri_engine.get_actual_people_request()
        actual_people = json.loads(actual_people_json)
        visible_ids = [int(fpid) for fpid, t in actual_people.items() if t < 1]

        faceprints_json = self.hri_engine.get_faceprint_request(json.dumps({"fields": ["id", "name"]}))
        faceprints = json.loads(faceprints_json)
        id_to_name = {int(fp["id"]): fp["name"] for fp in faceprints}

        visible_people = [id_to_name[pid] for pid in visible_ids if pid in id_to_name]
        known_people = list(id_to_name.values())

        sessions_summary_json = self.hri_engine.get_sessions_summary_request()
        sessions_summary = json.loads(sessions_summary_json)

        times_seen = {}
        last_seen = {}
        for summary in sessions_summary:
            fp_id = int(summary["faceprint_id"])
            name = id_to_name.get(fp_id)
            if not name: # Esta persona ya no existe (habria q hacer q borrar un faceprint lo borre de sessions)
                continue
            
            dt = datetime.fromtimestamp(float(summary["last_seen"]))
            last_seen[name] = dt.strftime("%Y-%m-%d %H:%M")
            times_seen[name] = summary["sessions_count"]

        return {
            "visible_people": visible_people,
            "known_people": known_people,
            "times_seen": times_seen,
            "last_seen": last_seen
        }
