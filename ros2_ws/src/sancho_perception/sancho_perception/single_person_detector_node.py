#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nodo de detección/seguimiento robusto de una única persona con filtros temporales y espaciales (versión lifecycle).

- Suscribe:  /human_pose/persons_poses (PoseArray) [opcional msg.track_ids]
- Publica :  /detected_person (geometry_msgs/PoseStamped)
             /person_marker (visualization_msgs/Marker)

Parámetros
----------
min_detection_duration (float, 3.0):   Tiempo mínimo acumulado para considerar detectada la persona
position_tolerance     (float, 0.3):   Tolerancia de movimiento entre frames para contar como estable (m)
max_speed              (float, 2.0):   Velocidad máxima esperada (m/s) para gating
check_period           (float, 0.5):   Periodo del timer interno (s)
detection_timeout      (float, 2.0):   Rate-limit de publicación y vida del marcador (s)
message_timeout        (float, 2.0):   Reinicio si no llegan mensajes (s)
grace_period           (float, 1.0):   Mantener estado ante ausencias breves (s)
history_size           (int,   10):    Tamaño del buffer de estabilidad (frames)
history_required       (int,   5):     Frames consecutivos estables requeridos
prefer_tracked_ids     (bool, True):   Priorizar continuidad por track_id si está disponible
initial_pick_strategy  (str, 'nearest_origin'): 'nearest_origin' | 'first'
"""

import numpy as np
import rclpy
from rclpy.duration import Duration
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile

from geometry_msgs.msg import PoseArray, PoseStamped, Point, Quaternion
from visualization_msgs.msg import Marker

class SinglePersonDetectionNode(LifecycleNode):
    def __init__(self):
        super().__init__("single_person_detection_lifecycle")
        self.get_logger().info("Inicializando nodo de detección de UNA persona (lifecycle)...")

        # Parámetros
        self.declare_parameter("min_detection_duration", 3.0)
        self.declare_parameter("position_tolerance", 0.3)
        self.declare_parameter("max_speed", 2.0)
        self.declare_parameter("check_period", 0.5)
        self.declare_parameter("detection_timeout", 2.0)
        self.declare_parameter("message_timeout", 2.0)
        self.declare_parameter("grace_period", 1.0)
        self.declare_parameter("history_size", 10)
        self.declare_parameter("history_required", 5)
        self.declare_parameter("prefer_tracked_ids", True)
        self.declare_parameter("initial_pick_strategy", "nearest_origin")  # or 'first'

        # Pub/Sub/Timer
        self.person_pub = None
        self.marker_pub = None
        self.persons_sub = None
        self.timer = None

        # Estado interno
        self.last_msg_ts = None
        self.current_detected = False
        self.detection_start_time = None
        self.last_detection_time = None

        self.stable_count = 0
        self.history_size = 10
        self.history_required = 5
        self.absence_start = None

        self.tracked_id = None            # track_id objetivo
        self.last_position = None         # np.array([x,y])
        self.last_marker_id = 0

    # ---------------- Lifecycle ----------------
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        # Leer parámetros validados
        self.min_detection_duration = max(0.1, float(self.get_parameter("min_detection_duration").value))
        self.position_tolerance = max(0.0, float(self.get_parameter("position_tolerance").value))
        self.max_speed = max(0.0, float(self.get_parameter("max_speed").value))
        self.check_period = max(0.01, float(self.get_parameter("check_period").value))
        self.detection_timeout = max(0.0, float(self.get_parameter("detection_timeout").value))
        self.message_timeout = max(0.0, float(self.get_parameter("message_timeout").value))
        self.grace_period = max(0.0, float(self.get_parameter("grace_period").value))
        self.history_size = max(1, int(self.get_parameter("history_size").value))
        self.history_required = max(1, int(self.get_parameter("history_required").value))
        self.prefer_tracked_ids = bool(self.get_parameter("prefer_tracked_ids").value)
        self.initial_pick_strategy = str(self.get_parameter("initial_pick_strategy").value)

        if self.history_required > self.history_size:
            self.get_logger().warn("history_required > history_size, igualando ambos")
            self.history_required = self.history_size

        qos = QoSProfile(depth=10)
        self.person_pub = self.create_lifecycle_publisher(PoseStamped, "/detected_person", qos)
        self.marker_pub = self.create_lifecycle_publisher(Marker, "/person_marker", qos)

        self.get_logger().info("Nodo configurado.")
        return super().on_configure(state)

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo...")

        qos = QoSProfile(depth=10)
        self.persons_sub = self.create_subscription(
            PoseArray, "/human_pose/persons_poses", self.poses_callback, qos
        )
        self.timer = self.create_timer(self.check_period, self.timer_callback)

        self.get_logger().info("Nodo activo.")
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo...")
        if self.timer:
            self.timer.cancel()
        if self.persons_sub:
            self.destroy_subscription(self.persons_sub)
        self.get_logger().info("Nodo desactivado.")
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando recursos...")
        if self.timer:
            self.destroy_timer(self.timer)
        if self.person_pub:
            self.destroy_lifecycle_publisher(self.person_pub)
        if self.marker_pub:
            self.destroy_lifecycle_publisher(self.marker_pub)
        if self.persons_sub:
            self.destroy_subscription(self.persons_sub)
        self.get_logger().info("Recursos limpiados.")
        return super().on_cleanup(state)

    # ---------------- Callbacks ----------------
    def timer_callback(self) -> None:
        now = self.get_clock().now()
        # Timeout de publicación / estado
        if self.last_detection_time and (now - self.last_detection_time).nanoseconds / 1e9 > self.detection_timeout:
            # No reseteamos del todo: mantenemos objetivo si hay mensajes recientes
            self.current_detected = False

        # Si no llegan mensajes hace tiempo, reset total
        if self.last_msg_ts:
            gap = (now - self.last_msg_ts).nanoseconds / 1e9
            if gap > self.message_timeout:
                self.get_logger().warn(f"No llegan mensajes desde hace {gap:.2f}s. Reset total.")
                self.reset()

    def poses_callback(self, msg: PoseArray) -> None:
        now = rclpy.time.Time.from_msg(msg.header.stamp)
        self._check_message_gap(now)
        self.last_msg_ts = now

        poses = msg.poses
        if len(poses) < 1:
            # No hay nadie: aplicar periodo de gracia antes de resetear del todo
            if self.absence_start is None:
                self.absence_start = now
            elif (now - self.absence_start).nanoseconds / 1e9 > self.grace_period:
                self.get_logger().info("Sin personas detectadas más allá del grace_period. Reset.")
                self.reset()
            return
        else:
            self.absence_start = None

        # Extraer puntos válidos
        points = np.array([[p.position.x, p.position.y] for p in poses], dtype=float)
        mask = np.isfinite(points).all(axis=1)
        if not np.any(mask):
            self.get_logger().debug("Todas las posiciones inválidas. Reset suave.")
            self._soft_reset_positions()
            return
        points = points[mask]
        valid_indices = np.nonzero(mask)[0]

        # track_ids opcional
        ids = None
        if self.prefer_tracked_ids:
            try:
                tmp = list(msg.track_ids)  # tipo esperado en tu origen
                if len(tmp) == len(msg.poses):
                    ids = [tmp[i] for i in valid_indices]
                else:
                    raise AttributeError
            except AttributeError:
                ids = None

        # Seleccionar candidato
        cand_idx = self._select_candidate(points, ids, now)

        if cand_idx is None:
            # No se pudo asociar bajo gating; estrategia de inicio si no hay objetivo
            if self.tracked_id is None and points.shape[0] > 0:
                cand_idx = self._pick_initial(points)
            else:
                # Mantener estado si estamos en gracia
                return

        pos = points[cand_idx]
        cand_id = ids[cand_idx] if (ids is not None) else None

        # Gating de velocidad si ya teníamos posición previa
        if self.last_position is not None:
            dt = max(1e-3, (now - self.last_msg_ts).nanoseconds / 1e9)  # self.last_msg_ts ya actualizado al inicio
            dist = float(np.linalg.norm(pos - self.last_position))
            vmax = self.max_speed * dt + self.position_tolerance
            if dist > max(vmax, self.position_tolerance):
                # salto espurio: reiniciar estabilidad pero adoptar nueva hipótesis
                self.get_logger().debug(f"Gating por velocidad: dist={dist:.2f} > {vmax:.2f}. Reinicio estabilidad.")
                self.stable_count = 1
            else:
                # estable
                if dist <= self.position_tolerance:
                    self.stable_count += 1
                else:
                    self.stable_count = min(self.stable_count + 1, self.history_size)  # movimiento pero aceptable
        else:
            self.stable_count = 1

        # Actualizar estado de objetivo
        self.last_position = pos
        if cand_id is not None:
            self.tracked_id = cand_id

        # Comprobación de estabilidad temporal
        if self.stable_count < self.history_required:
            # Aún no estable el suficiente tiempo
            self.current_detected = False
            self.detection_start_time = None
            return

        # Arrancar conteo temporal si no estaba
        if not self.current_detected:
            self.current_detected = True
            self.detection_start_time = now
            return

        elapsed = (now - self.detection_start_time).nanoseconds / 1e9
        if elapsed >= self.min_detection_duration:
            # Publicar con rate-limit
            if (self.last_detection_time is None) or \
               ((now - self.last_detection_time).nanoseconds / 1e9 > self.detection_timeout):
                self.publish_person(pos, now, frame_id=msg.header.frame_id or "map")
                self.last_detection_time = now

    # ---------------- Lógica de selección ----------------
    def _select_candidate(self, points: np.ndarray, ids, now) -> int:
        """
        Devuelve índice del candidato dentro de 'points' o None si no hay asociación plausible.
        """
        if points.shape[0] == 0:
            return None

        # 1) Si tenemos tracked_id activo y está presente, devolverlo
        if ids is not None and self.tracked_id is not None:
            for i, tid in enumerate(ids):
                if tid == self.tracked_id:
                    return i

        # 2) Si tenemos última posición, elegir el más cercano bajo gating
        if self.last_position is not None:
            # Estimación dt: usamos check_period como mínimo si no hay timestamp previo
            dt = self.check_period
            if self.last_msg_ts is not None:
                # Nota: en poses_callback ya asignamos last_msg_ts=now al inicio;
                # para el gating usamos el periodo esperado (check_period)
                dt = max(self.check_period, dt)
            dists = np.linalg.norm(points - self.last_position[None, :], axis=1)
            order = np.argsort(dists)
            for idx in order:
                vmax = self.max_speed * dt + self.position_tolerance
                if dists[idx] <= max(vmax, self.position_tolerance):
                    return idx
            return None

        # 3) Si no hay estado previo, que decida _pick_initial
        return None

    def _pick_initial(self, points: np.ndarray) -> int:
        if self.initial_pick_strategy == "first":
            return 0
        # nearest_origin por defecto
        dists0 = np.linalg.norm(points, axis=1)
        return int(np.argmin(dists0))

    # ---------------- Utilidades ----------------
    def _check_message_gap(self, now: rclpy.time.Time) -> None:
        if self.last_msg_ts is None:
            return
        gap = (now - self.last_msg_ts).nanoseconds / 1e9
        if gap > self.message_timeout:
            self.get_logger().warn(f"Gap de mensajes {gap:.2f}s > message_timeout. Reset suave.")
            self._soft_reset_positions()

    def _soft_reset_positions(self):
        """Resetea estabilidad y última posición, conservando tracked_id por si reaparece."""
        self.stable_count = 0
        self.last_position = None
        self.current_detected = False
        self.detection_start_time = None
        # No tocamos self.tracked_id para intentar reconectar si vuelve

    def reset(self):
        """Reset completo del estado."""
        self.stable_count = 0
        self.last_position = None
        self.tracked_id = None
        self.current_detected = False
        self.detection_start_time = None
        self.last_detection_time = None
        self.absence_start = None

    # ---------------- Publicación ----------------
    def publish_person(self, pos_xy: np.ndarray, timestamp: rclpy.time.Time, frame_id: str = "map"):
        # PoseStamped
        ps = PoseStamped()
        ps.header.stamp = timestamp.to_msg()
        ps.header.frame_id = frame_id
        ps.pose.position = Point(x=float(pos_xy[0]), y=float(pos_xy[1]), z=0.0)
        ps.pose.orientation = Quaternion(w=1.0)  # sin orientación específica
        self.person_pub.publish(ps)

        # Marker (esfera pequeña)
        m = Marker()
        m.header.stamp = timestamp.to_msg()
        m.header.frame_id = frame_id
        m.ns = "person"
        m.id = self.last_marker_id  # reutilizamos el mismo id
        m.type = Marker.SPHERE
        m.action = Marker.ADD
        m.pose = ps.pose
        m.scale.x = 0.3
        m.scale.y = 0.3
        m.scale.z = 0.3
        m.color.r = 0.0
        m.color.g = 0.6
        m.color.b = 1.0
        m.color.a = 0.9
        m.lifetime = Duration(seconds=self.detection_timeout + 0.1).to_msg()
        self.marker_pub.publish(m)

        self.get_logger().info(
            f"Publicado PERSONA: ({pos_xy[0]:.2f}, {pos_xy[1]:.2f}) [frame={frame_id}]"
        )

def main(args=None):
    rclpy.init(args=args)
    node = SinglePersonDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
