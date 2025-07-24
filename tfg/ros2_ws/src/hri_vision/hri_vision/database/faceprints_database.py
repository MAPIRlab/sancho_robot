import os
import json

from datetime import datetime
from threading import RLock


class FaceprintsDatabase:
    def __init__(self, db_path='faceprints_db.json', db_mode="save"):
        self.db_mode = db_mode
        self.db_path = db_path
        self._lock = RLock()

        self.next_id = 0
        self.faceprints = {}

        self.load()

    def get_all_ids(self):
        with self._lock:
            return list(self.faceprints.keys())

    def get_all(self, name=""):
        with self._lock:
            return [fp for fp in self.faceprints.values() if not name or fp["name"].lower() == name.lower()]

    def get_by_id(self, id):
        with self._lock:
            return self.faceprints.get(id)

    def add(self, name, features, face, score):
        with self._lock:
            id = self.get_next_id()
            new_faceprint = {
                'id': id,
                'name': name,
                'face': face,
                'face_score': score,
                'features': [features],
                'size': [1],
                'learning_date': datetime.now().timestamp()
            }
            self.faceprints[id] = new_faceprint

            return new_faceprint

    def update(self, id, new_data):
        with self._lock:
            original_entry = self.get_by_id(id)
            if original_entry is None:
                return None # No existe

            for key, value in new_data.items(): # Actualizamos los campos
                if key in original_entry:
                    original_entry[key] = value

            return original_entry

    def remove(self, id):
        with self._lock:
            if id in self.faceprints:
                del self.faceprints[id]

    def get_next_id(self):
        with self._lock:
            id = self.next_id
            self.next_id = self.next_id + 1
            return str(id)

    def save(self):
        if self.db_mode != "save":
            return
        
        with self._lock:
            database = {
                "next_id": self.next_id,
                "faceprints": self.faceprints
            }

            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(database, f, indent=4)

    def load(self):
        if self.db_mode != "save":
            return
        
        with self._lock:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

            if not os.path.exists(self.db_path): # Si no existe, lo creamos vacio
                self.save()

            with open(self.db_path, "r", encoding="utf-8") as f:
                database = json.load(f)

                self.next_id = database["next_id"]
                self.faceprints = database["faceprints"]

