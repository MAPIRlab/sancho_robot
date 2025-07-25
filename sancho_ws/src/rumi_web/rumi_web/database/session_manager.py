from datetime import datetime
from typing import Optional
from .sessions_database import SessionsDatabase


class SessionManager:
    def __init__(self, db: SessionsDatabase, timeout_seconds: float = 5, time_between_detections: float = 1):
        self.db = db
        self.timeout_seconds = timeout_seconds
        self.time_between_detections = time_between_detections

        self.actual_people = {}
        self.active_sessions = {}  # faceprint_id -> SessionData

    def process_detection(self, faceprint_id: int, score_face: float, score_classification: float, face_image_base64: Optional[str] = None):
        now = datetime.now().timestamp()

        self.actual_people[faceprint_id] = now

        if faceprint_id not in self.active_sessions:
            self.active_sessions[faceprint_id] = {
                'faceprint_id': faceprint_id,
                'start_time': now,
                'detections': []
            }

        session = self.active_sessions[faceprint_id]

        last_detection_time = self._get_last_detection_time(session)
        if (now - last_detection_time) > self.time_between_detections:
            session['detections'].append([
                now,
                score_face,
                score_classification,
                face_image_base64 or ""
            ])

    def get_all_last_seen(self):
        actual_people_time = {}
        for key, value in self.actual_people.items():
            actual_people_time[key] = datetime.now().timestamp() - value
        return actual_people_time
    
    def get_last_seen(self, faceprint_id):
        return datetime.now().timestamp() - self.actual_people.get(faceprint_id, 0)

    def check_timeouts(self):
        now = datetime.now().timestamp()

        to_close = []
        for faceprint_id, session in self.active_sessions.items():
            last_detection_time = self._get_last_detection_time(session, now)
            if (now - last_detection_time) > self.timeout_seconds:
                to_close.append(faceprint_id)
        
        for faceprint_id in to_close:
            print(f"Cerrando la sesión de {faceprint_id}")
            self._close_session(faceprint_id)
    
    def _close_session(self, faceprint_id: int):
        session = self.active_sessions.pop(faceprint_id, None)
        if session is None:
            return

        session_data = {
            'faceprint_id': session['faceprint_id'],
            'start_time': session['start_time'],
            'end_time': session['detections'][-1][0],
            'detections': session['detections']
        }

        self.db.create_session_with_detections(session_data)

    def _get_last_detection_time(self, session, default=0):
        return default if len(session['detections']) == 0 else session['detections'][-1][0]