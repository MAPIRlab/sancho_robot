#!/usr/bin/env python3

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
from tf2_geometry_msgs import (
    do_transform_pose_stamped,  # <- Esto es lo que registra el tipo
)
from tf2_ros import (
    ConnectivityException,
    ExtrapolationException,
    LookupException,
    TransformException,
)
from visualization_msgs.msg import Marker, MarkerArray

_ = do_transform_pose_stamped

from sancho_msgs.msg import GroupInfo


class GroupWaypointGeneratorNode(LifecycleNode):
    """GroupWaypointGeneratorNode: A ROS 2 lifecycle node that generates navigation waypoints around detected groups.

    This node subscribes to group detection information, calculates appropriate waypoints for a robot to
    approach the group while maintaining a safe distance, and publishes these waypoints as navigation goals.
    It also publishes visualization markers for RViz.

    The node follows the managed lifecycle pattern from ROS 2, implementing configure, activate, deactivate,
    cleanup, and shutdown transitions.

    Parameters
    ----------
        group_topic (string): Topic for subscribing to detected group information
        waypoint_goal_topic (string): Topic for publishing waypoint goals
        safety_margin (float): Additional distance from group perimeter for waypoint placement
        goal_update_threshold (float): Minimum distance change required to publish a new waypoint
        robot_frame (string): TF frame ID for the robot base
        tf_lookup_timeout (float): Timeout for TF transformations in seconds
        goal_history_size (int): Size of waypoint history buffer for filtering
        waypoint_marker_topic (string): Topic for publishing visualization markers
        waypoint_marker_lifetime (float): Duration in seconds for marker visibility

    Subscriptions:
        {group_topic} (GroupInfo): Information about detected groups

    Publications:
        {waypoint_goal_topic} (PoseStamped): Generated waypoint goal
        {waypoint_marker_topic} (MarkerArray): Visualization markers for RViz

    The node computes waypoints that position the robot at a safe distance from the group's perimeter,
    orienting the robot to face the group. It uses a history-based filter to reduce goal thrashing
    by only publishing significantly different waypoints.

    """

    def __init__(self):
        super().__init__("group_waypoint_generator_lifecycle")
        self.get_logger().info(
            "Inicializando nodo de generación de waypoints con Lifecycle..."
        )

        # Parámetros de tópicos y detección
        self.declare_parameter("group_topic", "/detected_group")
        self.declare_parameter("waypoint_goal_topic", "/group_waypoint")
        self.declare_parameter("safety_margin", 0.5)
        self.declare_parameter("goal_update_threshold", 0.1)
        self.declare_parameter("robot_frame", "base_link")
        self.declare_parameter("tf_lookup_timeout", 0.1)
        self.declare_parameter("goal_history_size", 5)
        self.declare_parameter("waypoint_marker_topic", "/waypoint_marker_array")
        self.declare_parameter("waypoint_marker_lifetime", 1.0)

        # Recursos internos
        self.group_sub = None
        self.goal_pub = None
        self.marker_pub = None
        self.goal_history: deque[np.ndarray] = deque()

        # TF2 para obtener pose del robot
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        # Carga de parámetros
        self.group_topic = self.get_parameter("group_topic").value
        self.waypoint_goal_topic = self.get_parameter("waypoint_goal_topic").value
        self.safety_margin = self.get_parameter("safety_margin").value
        self.goal_update_threshold = self.get_parameter("goal_update_threshold").value
        self.robot_frame = self.get_parameter("robot_frame").value
        self.tf_lookup_timeout = self.get_parameter("tf_lookup_timeout").value
        self.goal_history_size = int(self.get_parameter("goal_history_size").value)
        self.waypoint_marker_topic = self.get_parameter("waypoint_marker_topic").value
        self.waypoint_marker_lifetime = self.get_parameter(
            "waypoint_marker_lifetime"
        ).value

        # Inicializar historial de waypoints
        self.goal_history = deque(maxlen=self.goal_history_size)

        # Publicadores lifecycle
        self.goal_pub = self.create_lifecycle_publisher(
            PoseStamped, self.waypoint_goal_topic, 10
        )
        self.marker_pub = self.create_lifecycle_publisher(
            MarkerArray, self.waypoint_marker_topic, 10
        )

        return super().on_configure(state)

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo...")

        qos = QoSProfile(depth=10)
        self.group_sub = self.create_subscription(
            GroupInfo, self.group_topic, self.group_callback, qos
        )

        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo...")
        if self.group_sub:
            self.destroy_subscription(self.group_sub)
            self.group_sub = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando recursos del nodo...")
        if self.group_sub:
            self.destroy_subscription(self.group_sub)
            self.group_sub = None
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
        if self.group_sub:
            self.destroy_subscription(self.group_sub)
            self.group_sub = None
        if self.goal_pub:
            self.destroy_publisher(self.goal_pub)
            self.goal_pub = None
        if self.marker_pub:
            self.destroy_publisher(self.marker_pub)
            self.marker_pub = None
        return super().on_shutdown(state)

    def group_callback(self, msg: GroupInfo) -> None:
        """Procesa un GroupInfo, calcula un waypoint seguro y publica goal + marcadores."""
        frame_id = msg.header.frame_id
        stamp = msg.header.stamp

        # Extracción de datos
        try:
            centroid = np.array(
                [
                    msg.pose.position.x,
                    msg.pose.position.y,
                ],
                dtype=float,
            )
            radius = float(msg.radius)
        except (AttributeError, TypeError) as e:
            self.get_logger().error(f"Error al procesar GroupInfo: {e}")
            return

        # Validar valores
        if radius < 0:
            self.get_logger().warn(f"Radio negativo ({radius}). Ignorando.")
            return
        if self.safety_margin < 0:
            self.get_logger().warn(
                f"Safety_margin negativa ({self.safety_margin}). Usando absoluto."
            )
            self.safety_margin = abs(self.safety_margin)

        centroid_map = self.transform_centroid_to_map(centroid, frame_id, stamp)
        if centroid_map is None:
            self.get_logger().warn("No se pudo transformar el centroide a 'map'.")
            return

        robot_pos = self.get_robot_position("map", stamp)
        if robot_pos is None:
            self.get_logger().warn("No se pudo obtener la pose del robot en 'map'.")
            return

        # Calcular waypoint
        goal_point = self.compute_waypoint(centroid_map, radius, robot_pos)

        # Decidir si actualizar según historial
        if not self.should_update_goal(goal_point):
            self.get_logger().info("Waypoint similar al histórico. No se actualiza.")
            return

        # Guardar en historial y publicar
        self.goal_history.append(goal_point)
        goal_msg = self.make_goal_msg(goal_point, centroid_map)
        self.goal_pub.publish(goal_msg)
        self.get_logger().info(f"Publicado objetivo en {goal_point.tolist()}")

        # Publicar marcadores en RViz
        self.publish_markers(goal_msg, centroid_map)

    def transform_centroid_to_map(
        self, centroid: np.ndarray, source_frame: str, stamp
    ) -> np.ndarray | None:
        """Crea un PoseStamped con el centroide en source_frame y lo transforma a 'map'.
        Devuelve un array [x, y] en map, o None si falla.
        """
        # 1) Empaqueta el centroide en un PoseStamped
        ps = PoseStamped()
        ps.header.frame_id = source_frame
        ps.header.stamp = stamp
        ps.pose.position.x = float(centroid[0])
        ps.pose.position.y = float(centroid[1])
        ps.pose.position.z = 0.0
        ps.pose.orientation.w = 1.0  # sin rotación

        # 2) Pide el transform de source_frame → map
        try:
            tf = self.tf_buffer.lookup_transform(
                "map",
                source_frame,
                rclpy.time.Time.from_msg(stamp),
                timeout=Duration(seconds=self.tf_lookup_timeout),
            )
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"TF2 lookup failed for centroid: {e}")
            return None

        # 3) Aplica la transformación
        try:
            ps_map = do_transform_pose_stamped(ps, tf)
        except TransformException as e:
            self.get_logger().warn(f"Error al transformar centroid: {e}")
            return None

        return np.array([ps_map.pose.position.x, ps_map.pose.position.y], dtype=float)

    def get_robot_position(
        self, target_frame: str, stamp
    ) -> np.ndarray | None:  # noqa: F821
        """Usa TF2 para obtener la posición del robot en el frame objetivo."""
        try:
            t = self.tf_buffer.lookup_transform(
                target_frame,
                self.robot_frame,
                rclpy.time.Time.from_msg(stamp),
                timeout=Duration(seconds=self.tf_lookup_timeout),
            ).transform.translation
            return np.array([t.x, t.y], dtype=float)
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"TF2 lookup failed: {e}")
            return None

    def compute_waypoint(
        self,
        centroid: np.ndarray,
        radius: float,
        robot_pos: np.ndarray,
    ) -> np.ndarray:
        """Calcula el punto de aproximación considerando safety_margin."""
        vec = robot_pos - centroid
        norm = np.linalg.norm(vec)
        if norm < 1e-3:
            self.get_logger().warn("Robot en el centro del grupo. Direc. X positiva.")
            direction = np.array([1.0, 0.0])
        else:
            direction = vec / norm

        self.get_logger().info(
            f"Centroid map: {centroid.tolist()}, robot: {robot_pos.tolist()}"
        )
        self.get_logger().info(
            f"Vec = robot - centroid = {(robot_pos - centroid).tolist()}, norm = {norm:.3f}, direction = {direction.tolist()}"
        )
        self.get_logger().info(
            f"Waypoint result: { (centroid + (radius + self.safety_margin)*direction).tolist() }"
        )

        return centroid + (radius + self.safety_margin) * direction

    def should_update_goal(self, goal_point: np.ndarray) -> bool:
        """Decide si publicar un nuevo waypoint según distancia media al historial."""
        if not self.goal_history:
            return True
        avg = np.mean(np.vstack(self.goal_history), axis=0)
        diff = np.linalg.norm(goal_point - avg)
        return diff >= self.goal_update_threshold

    def make_goal_msg(self, point: np.ndarray, centroid: np.ndarray) -> PoseStamped:
        """Crea un PoseStamped orientado hacia el grupo."""
        vec = centroid - point
        yaw = math.atan2(vec[1], vec[0])
        q = self.yaw_to_quaternion(yaw)

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position = Point(x=float(point[0]), y=float(point[1]), z=0.0)
        msg.pose.orientation = q

        return msg

    def publish_markers(
        self,
        goal_point: PoseStamped,
        centroid: np.ndarray,
    ) -> None:
        """Publica en RViz un punto y una flecha mostrando el waypoint."""
        ma = MarkerArray()

        # Punto de waypoint
        m_p = Marker()
        m_p.header = goal_point.header
        m_p.ns = "waypoint_point"
        m_p.id = 0
        m_p.type = Marker.SPHERE
        m_p.action = Marker.ADD
        m_p.pose.position = goal_point.pose.position
        m_p.pose.orientation = Quaternion(w=1.0)
        m_p.scale.x = m_p.scale.y = m_p.scale.z = 0.2
        m_p.color.r = 1.0
        m_p.color.g = 0.0
        m_p.color.b = 0.0
        m_p.color.a = 0.8
        m_p.lifetime = Duration(
            seconds=self.get_parameter("waypoint_marker_lifetime").value
        ).to_msg()
        ma.markers.append(m_p)

        # Flecha hacia el grupo
        vec = centroid - np.array(
            [goal_point.pose.position.x, goal_point.pose.position.y], dtype=float
        )

        yaw = math.atan2(vec[1], vec[0])
        q = self.yaw_to_quaternion(yaw)
        dist = np.linalg.norm(vec)

        m_a = Marker()
        m_a.header = goal_point.header
        m_a.ns = "waypoint_arrow"
        m_a.id = 1
        m_a.type = Marker.ARROW
        m_a.action = Marker.ADD
        m_a.pose.position = goal_point.pose.position
        m_a.pose.orientation = q
        m_a.scale.x = dist
        m_a.scale.y = 0.05
        m_a.scale.z = 0.05
        m_a.color.r = 0.0
        m_a.color.g = 0.0
        m_a.color.b = 1.0
        m_a.color.a = 0.8
        m_a.lifetime = Duration(
            seconds=self.get_parameter("waypoint_marker_lifetime").value
        ).to_msg()
        ma.markers.append(m_a)

        self.marker_pub.publish(ma)

    def yaw_to_quaternion(self, yaw: float) -> Quaternion:
        q_arr = tf_transformations.quaternion_from_euler(0, 0, yaw)
        return Quaternion(x=q_arr[0], y=q_arr[1], z=q_arr[2], w=q_arr[3])


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GroupWaypointGeneratorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
