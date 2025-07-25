import os
import json

import rclpy
from rclpy.node import Node

from rumi_msgs.msg import SessionMessage
from rumi_msgs.srv import GetString, SetSessionParams

from .database.sessions_database import SessionsDatabase
from .database.session_manager import SessionManager


class SessionManagerNode(Node):
    def __init__(self):
        super().__init__('api_client_node')

        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "database/sessions.db"))
        self.db = SessionsDatabase(self.db_path)
        self.sessions = SessionManager(self.db, timeout_seconds=15.0, time_between_detections=0.0)

        self.session_sub = self.create_subscription(SessionMessage, 'rumi/sessions/process', self.session_callback, 10)

        self.get_sessions_serv = self.create_service(GetString, 'rumi/sessions/get', self.get_sessions_service)
        self.get_sessions_summary_serv = self.create_service(GetString, 'rumi/sessions/get_summary', self.get_sessions_summary_service)
        self.set_params_serv = self.create_service(SetSessionParams, 'rumi/sessions/set_params', self.set_session_params_service)

        self.get_logger().info("Session Manager Node initializated succesfully")
        self.create_timer(10.0, self.sessions.check_timeouts)

    def set_session_params_service(self, request, response):
        self.sessions.timeout_seconds = request.timeout_seconds
        self.sessions.time_between_detections = request.time_between_detections

        response.success = True
        response.message = (
            f"Parámetros actualizados: timeout_seconds={request.timeout_seconds}, "
            f"time_between_detections={request.time_between_detections}"
        )
        self.get_logger().info(response.message)

        return response

    def session_callback(self, msg):
        self.sessions.process_detection(str(msg.faceprint_id), float(msg.detection_score), float(msg.classification_score))

    def get_sessions_service(self, request, response):
        args = request.args

        if args:
            args = json.loads(args)

            id = args.get("id", None)
            faceprint_id = args.get("faceprint_id", None)
            if id is not None:
                item = self.db.get_session_by_id(id)
                response.text = json.dumps(item)
            elif faceprint_id is not None:
                items = self.db.get_sessions_by_faceprint_id(faceprint_id)
                response.text = json.dumps(items)
        else:
            items = self.db.get_all_sessions()
            response.text = json.dumps(items)

        return response

    def get_sessions_summary_service(self, request, response):
        """
        faceprint_id	Identificador del usuario (único).
        sessions_count	Número de sesiones totales de ese usuario.
        times_seen	Total de detecciones.
        first_seen	Primer start_time entre todas sus sesiones.
        last_seen	Último detections[-1][0] o end_time si no hay detections.
        total_duration	Suma de (end - start) por sesión.
        avg_session_duration	Promedio de duración de sesiones.
        avg_detections_per_session	Promedio de detecciones por sesión.
        """
        
        args = request.args

        if args:
            args = json.loads(args)
            faceprint_id_filter = args.get("faceprint_id", None)
            sessions = self.db.get_sessions_by_faceprint_id(faceprint_id_filter) if faceprint_id_filter is not None else self.db.get_all_sessions()
        else:
            sessions = self.db.get_all_sessions()

        summary = {}

        for session in sessions:
            faceprint_id = session["faceprint_id"]
            start_time = float(session["start_time"])
            end_time = float(session["end_time"])
            detections = session.get("detections", [])
            last_seen = float(detections[-1][0]) if detections else end_time
            times_seen = len(detections)
            duration = end_time - start_time

            if faceprint_id not in summary:
                summary[faceprint_id] = {
                    "faceprint_id": faceprint_id,
                    "sessions_count": 0,
                    "times_seen": 0,
                    "first_seen": start_time,
                    "last_seen": last_seen,
                    "total_duration": 0.0,
                    "total_detections": 0
                }

            s = summary[faceprint_id]
            s["sessions_count"] += 1
            s["times_seen"] += times_seen
            s["total_duration"] += duration
            s["total_detections"] += times_seen
            s["first_seen"] = min(s["first_seen"], start_time)
            s["last_seen"] = max(s["last_seen"], last_seen)

        result = []
        for stats in summary.values():
            sessions_count = stats["sessions_count"]
            stats["avg_session_duration"] = round(stats["total_duration"] / sessions_count, 2) if sessions_count else 0.0
            stats["avg_detections_per_session"] = round(stats["total_detections"] / sessions_count, 2) if sessions_count else 0.0
            stats["total_duration"] = round(stats["total_duration"], 2)
            stats["first_seen"] = str(stats["first_seen"])
            stats["last_seen"] = str(stats["last_seen"])
            result.append(stats)

        response.text = json.dumps(result)
        
        return response

def main(args=None):
    rclpy.init(args=args)

    session_manager_node = SessionManagerNode()
    rclpy.spin(session_manager_node)

    rclpy.shutdown()