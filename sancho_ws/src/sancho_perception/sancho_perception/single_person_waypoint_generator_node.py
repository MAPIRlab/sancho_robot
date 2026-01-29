#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
from collections import deque

import numpy as np
import rclpy
import tf2_ros
import tf_transformations  # pip install tf-transformations
from geometry_msgs.msg import Point, PoseStamped, Quaternion
from rclpy.duration import Duration
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile
from tf2_geometry_msgs import do_transform_pose_stamped
from tf2_ros import (
    ConnectivityException,
    ExtrapolationException,
    LookupException,
    TransformException,
)
from visualization_msgs.msg import Marker, MarkerArray


class PersonWaypointGeneratorNode(LifecycleNode):

    def __init__(self):
        super().__init__("person_waypoint_generator_lifecycle")
        self.get_logger().info("Inicializando nodo de waypoints para UNA persona (Lifecycle)...")

        # Parámetros
        self.declare_parameter("person_topic", "/detected_person")
        self.declare_parameter("waypoint_goal_topic", "/person_waypoint")
        self.declare_parameter("stand_off_distance", 0.3)
        self.declare_parameter("goal_update_threshold", 0.15)
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("tf_lookup_timeout", 0.1)
        self.declare_parameter("goal_history_size", 5)
        self.declare_parameter("waypoint_marker_topic", "/person_waypoint_marker_array")
        self.declare_parameter("waypoint_marker_lifetime", 1.0)

        # Recursos
        self.person_sub = None
        self.goal_pub = None
        self.marker_pub = None
        self.goal_history: deque[np.ndarray] = deque()

        # TF2
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

    # ---------------- Lifecycle ----------------
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        self.person_topic = self.get_parameter("person_topic").value
        self.waypoint_goal_topic = self.get_parameter("waypoint_goal_topic").value
        self.stand_off_distance = float(self.get_parameter("stand_off_distance").value)
        self.goal_update_threshold = float(self.get_parameter("goal_update_threshold").value)
        self.robot_frame = self.get_parameter("robot_frame").value
        self.tf_lookup_timeout = float(self.get_parameter("tf_lookup_timeout").value)
        self.goal_history_size = int(self.get_parameter("goal_history_size").value)
        self.waypoint_marker_topic = self.get_parameter("waypoint_marker_topic").value
        self.waypoint_marker_lifetime = float(self.get_parameter("waypoint_marker_lifetime").value)

        self.goal_history = deque(maxlen=self.goal_history_size)

        # Publishers lifecycle
        self.goal_pub = self.create_lifecycle_publisher(PoseStamped, self.waypoint_goal_topic, 10)
        self.marker_pub = self.create_lifecycle_publisher(MarkerArray, self.waypoint_marker_topic, 10)

        return super().on_configure(state)

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo...")
        qos = QoSProfile(depth=10)
        self.person_sub = self.create_subscription(
            PoseStamped, self.person_topic, self.person_callback, qos
        )
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo...")
        if self.person_sub:
            self.destroy_subscription(self.person_sub)
            self.person_sub = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando recursos...")
        if self.person_sub:
            self.destroy_subscription(self.person_sub)
            self.person_sub = None
        if self.goal_pub:
            self.destroy_lifecycle_publisher(self.goal_pub)
            self.goal_pub = None
        if self.marker_pub:
            self.destroy_lifecycle_publisher(self.marker_pub)
            self.marker_pub = None
        self.goal_history.clear()
        return super().on_cleanup(state)

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Apagando nodo...")
        if self.person_sub:
            self.destroy_subscription(self.person_sub)
            self.person_sub = None
        if self.goal_pub:
            self.destroy_publisher(self.goal_pub)
            self.goal_pub = None
        if self.marker_pub:
            self.destroy_publisher(self.marker_pub)
            self.marker_pub = None
        return super().on_shutdown(state)

    # ---------------- Callback principal ----------------
    def person_callback(self, msg: PoseStamped) -> None:
        """Procesa la pose de la persona, genera waypoint y publica goal + marcadores."""
        frame_id = msg.header.frame_id or "map"
        stamp = msg.header.stamp

        # 1) Transformar persona a 'map'
        p_map = self.transform_pose_to_map(msg, target_frame="map")
        if p_map is None:
            self.get_logger().warn("No se pudo transformar la persona a 'map'.")
            return
        person_xy = np.array([p_map.pose.position.x, p_map.pose.position.y], dtype=float)

        # 2) Pose del robot en 'map'
        robot_xy = self.get_robot_xy("map", stamp)
        if robot_xy is None:
            self.get_logger().warn("No se pudo obtener la pose del robot en 'map'.")
            return

        # 3) Calcular waypoint a stand-off mirando a la persona
        goal_xy = self.compute_waypoint(person_xy, robot_xy, self.stand_off_distance)
        

        # 4) Filtrado por histórico
        if not self.should_update_goal(goal_xy):
            self.get_logger().info("Waypoint similar al histórico. No se actualiza.")
            return

        self.goal_history.append(goal_xy)
        # TODO: Revisar el código a partir de aquí, al generar el goal msg la pose se ve detras de la psoicon del robot!

        # 5) Publicar objetivo y marcadores
        goal_msg = self.make_goal_msg(goal_xy, person_xy)
        self.goal_pub.publish(goal_msg)
        self.get_logger().info(f"Publicado objetivo en {goal_xy.tolist()} mirando a persona {person_xy.tolist()}")
        self.publish_markers(goal_msg, person_xy)

    # ---------------- Utilidades de TF ----------------
    def transform_pose_to_map(self, pose_stamped: PoseStamped, target_frame: str) -> PoseStamped | None:
        """Transforma un PoseStamped a target_frame usando TF2."""
        try:
            tf = self.tf_buffer.lookup_transform(
                target_frame,
                pose_stamped.header.frame_id or target_frame,
                rclpy.time.Time.from_msg(pose_stamped.header.stamp),
                timeout=Duration(seconds=self.tf_lookup_timeout),
            )
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"TF2 lookup failed: {e}")
            return None

        try:
            return do_transform_pose_stamped(pose_stamped, tf)
        except TransformException as e:
            self.get_logger().warn(f"Error al transformar pose: {e}")
            return None

    def get_robot_xy(self, target_frame: str, stamp) -> np.ndarray | None:
        """Obtiene (x,y) de robot_frame en target_frame."""
        try:
            t = self.tf_buffer.lookup_transform(
                target_frame, self.robot_frame, rclpy.time.Time.from_msg(stamp),
                timeout=Duration(seconds=self.tf_lookup_timeout),
            ).transform.translation
            return np.array([t.x, t.y], dtype=float)
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"TF2 lookup failed (robot): {e}")
            return None

    # ---------------- Lógica de waypoint ----------------
    def compute_waypoint(self, person_xy: np.ndarray, robot_xy: np.ndarray, stand_off: float) -> np.ndarray:
        """Coloca el waypoint sobre el círculo de radio stand_off centrado en la persona,
        en la dirección desde la persona hacia el robot. Si robot y persona coinciden, usa +X.
        """
        vec = person_xy - robot_xy
        distance = float(np.linalg.norm(vec))
        stand_off = abs(float(stand_off))

        if distance < 1e-3:
            self.get_logger().warn("Robot y persona casi coinciden; usando dirección +X.")
            direction = np.array([1.0, 0.0], dtype=float)
            goal_xy = person_xy + stand_off * direction
            used_offset = stand_off
        else:
            direction = vec / distance
            offset = min(distance, stand_off)
            goal_xy = person_xy - offset * direction
            used_offset = offset

        self.get_logger().info(
            f"Persona(map)={person_xy.tolist()} Robot(map)={robot_xy.tolist()} "
            f"-> Goal={goal_xy.tolist()} (offset={used_offset:.2f})"
        )
        return goal_xy

    def should_update_goal(self, goal_xy: np.ndarray) -> bool:
        """Publica solo si el nuevo objetivo se diferencia lo suficiente del promedio histórico."""
        if not self.goal_history:
            return True
        avg = np.mean(np.vstack(self.goal_history), axis=0)
        diff = float(np.linalg.norm(goal_xy - avg))
        return diff >= float(self.goal_update_threshold)

    def make_goal_msg(self, goal_xy: np.ndarray, person_xy: np.ndarray) -> PoseStamped:
        """Crea un PoseStamped en 'map' orientado a la persona."""
        vec = person_xy - goal_xy
        yaw = math.atan2(vec[1], vec[0])
        q = self.yaw_to_quaternion(yaw)

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position = Point(x=float(goal_xy[0]), y=float(goal_xy[1]), z=0.0)
        msg.pose.orientation = q
        return msg

    def publish_markers(self, goal_msg: PoseStamped, person_xy_map: np.ndarray) -> None:
        """Publica esfera del waypoint + flecha hacia la persona."""
        ma = MarkerArray()

        # Punto del waypoint
        m_p = Marker()
        m_p.header = goal_msg.header
        m_p.ns = "person_waypoint_point"
        m_p.id = 0
        m_p.type = Marker.SPHERE
        m_p.action = Marker.ADD
        m_p.pose.position = goal_msg.pose.position
        m_p.pose.orientation = Quaternion(w=1.0)
        m_p.scale.x = m_p.scale.y = m_p.scale.z = 0.22
        m_p.color.r = 1.0
        m_p.color.g = 0.2
        m_p.color.b = 0.2
        m_p.color.a = 0.85
        m_p.lifetime = Duration(seconds=self.waypoint_marker_lifetime).to_msg()
        ma.markers.append(m_p)

        # Flecha mirando a la persona
        vec = person_xy_map - np.array([goal_msg.pose.position.x, goal_msg.pose.position.y], dtype=float)
        dist = float(np.linalg.norm(vec))
        yaw = math.atan2(vec[1], vec[0])
        q = self.yaw_to_quaternion(yaw)

        m_a = Marker()
        m_a.header = goal_msg.header
        m_a.ns = "person_waypoint_arrow"
        m_a.id = 1
        m_a.type = Marker.ARROW
        m_a.action = Marker.ADD
        m_a.pose.position = goal_msg.pose.position
        m_a.pose.orientation = q
        m_a.scale.x = max(dist, 0.05)  # longitud
        m_a.scale.y = 0.06
        m_a.scale.z = 0.06
        m_a.color.r = 0.2
        m_a.color.g = 0.2
        m_a.color.b = 1.0
        m_a.color.a = 0.85
        m_a.lifetime = Duration(seconds=self.waypoint_marker_lifetime).to_msg()
        ma.markers.append(m_a)

        self.marker_pub.publish(ma)

    @staticmethod
    def yaw_to_quaternion(yaw: float) -> Quaternion:
        qx, qy, qz, qw = tf_transformations.quaternion_from_euler(0.0, 0.0, yaw)
        return Quaternion(x=qx, y=qy, z=qz, w=qw)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PersonWaypointGeneratorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
