import time
import threading
import numpy as np

class SmartRecognitionCache:
    def __init__(self, ttl: float, max_size: int, cooldown_sec: float, move_thresh: float, reid_interval: float, lower_bound: float):
        self.entries = {}
        self.lock = threading.Lock()
        
        self.ttl = ttl
        self.max_size = max_size
        self.cooldown_sec = cooldown_sec
        self.move_thresh = move_thresh
        self.reid_interval = reid_interval
        self.lower_bound = lower_bound

    def get_action_and_entry(self, tid: int, corner_x: float, corner_y: float, now: float):
        """Evalúa si debemos lanzar la IA para este TID y devuelve el mejor resultado guardado."""
        with self.lock:
            if tid not in self.entries:
                return 'TRIGGER', None

            entry = self.entries[tid]
            entry['last_seen'] = now

            if entry.get('processing', False):
                return 'WAIT', entry

            # Gestión de "No hay cara" (espaldas)
            if entry.get('no_face', False):
                last_pos = entry.get('last_inference_pos', (corner_x, corner_y))
                dist_moved = np.hypot(corner_x - last_pos[0], corner_y - last_pos[1])
                time_since = now - entry.get('last_inference_time', 0)
                
                if dist_moved >= self.move_thresh or time_since >= self.cooldown_sec:
                    return 'TRIGGER', entry
                return 'WAIT', entry

            # Re-identificación periódica para mejorar distancias malas
            if entry.get('distance', 1.0) < self.lower_bound:
                time_since = now - entry.get('last_inference_time', 0)
                if time_since > self.reid_interval:
                    return 'TRIGGER', entry

            return 'READY', entry

    def mark_processing(self, tid: int, corner_x: float, corner_y: float, now: float):
        with self.lock:
            if tid not in self.entries:
                self.entries[tid] = {'last_seen': now}
            self.entries[tid]['processing'] = True
            self.entries[tid]['last_inference_time'] = now
            self.entries[tid]['last_inference_pos'] = (corner_x, corner_y)

    def commit_result(self, tid: int, result: dict):
        with self.lock:
            if tid not in self.entries: return
            
            distance = result['distance']
            current_best = self.entries[tid].get('distance', float('inf'))
            is_new_better = distance < current_best

            if is_new_better or self.entries[tid].get('no_face', False):
                # Aplicamos el filtro matemático de identidad aquí
                if distance < self.lower_bound:
                    result['faceprint'] = {'id': '', 'name': 'Unknown'}

                self.entries[tid].update({
                    'face_aligned': result['face_aligned'],
                    'features':     result['features'],
                    'faceprint':    result['faceprint'],
                    'distance':     distance,
                    'pos':          result['pos'],
                    'face_updated': False,
                    'no_face':      False
                })
            self.entries[tid]['processing'] = False

    def commit_no_face(self, tid: int):
        with self.lock:
            if tid in self.entries:
                self.entries[tid]['processing'] = False
                if 'distance' not in self.entries[tid] or self.entries[tid]['distance'] >= self.lower_bound:
                    self.entries[tid]['no_face'] = True

    def abort_inference(self, tid: int):
        with self.lock:
            if tid in self.entries:
                self.entries[tid]['processing'] = False

    def force_training_update(self, tid: int, name: str, face_id: str):
        with self.lock:
            if tid in self.entries:
                if name:
                    self.entries[tid]['faceprint']['name'] = name
                if face_id:
                    self.entries[tid]['faceprint']['id'] = str(face_id)
                self.entries[tid]['distance'] = 1.0

    def prune_and_cleanup(self, now: float, cleanup_timeout: float):
        with self.lock:
            expired = [tid for tid, e in self.entries.items() 
                       if (now - e.get('last_seen', 0)) > min(self.ttl, cleanup_timeout)]
            for tid in expired:
                del self.entries[tid]

            if len(self.entries) > self.max_size:
                sorted_ids = sorted(self.entries.items(), key=lambda kv: kv[1].get('last_seen', 0))
                for tid, _ in sorted_ids[:len(self.entries) - self.max_size]:
                    del self.entries[tid]