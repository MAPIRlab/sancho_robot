#!/usr/bin/env python3
"""Nodo de ROS2 (Humble) mejorado para roaming aleatorio del robot usando Nav2.
Incluye validación de path mediante acción ComputePathToPose y generación de objetivos
relativos a la posición actual dentro de una ventana local.
"""
import math
import random

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.node import Node
from tf2_ros import (
    Buffer,
    ConnectivityException,
    ExtrapolationException,
    LookupException,
    TransformListener,
)
from tf_transformations import quaternion_from_euler

from sancho_msgs.srv import SetHome


class RoamingNode(Node):
    """RoamingNode: Autonomous Navigation Node for Robot Exploration

    This ROS2 node implements an autonomous roaming behavior that allows a robot to navigate
    randomly within an environment while respecting navigation constraints. The node generates
    random goal poses, validates them by checking path feasibility, and navigates to them using
    Nav2's action servers.

    Key Features:
    - Autonomous navigation to randomly generated valid poses
    - Local window constraint option to keep goals within a certain range of current position
    - Home position concept with automatic return when the robot exceeds maximum distance
    - Path validation to ensure goals are reachable and within configured path length limits
    - Goal history to prevent revisiting recent locations
    - Configurable parameters for customizing roaming behavior

    The node interfaces with Nav2 through:
    - NavigateToPose action client for executing navigation
    - ComputePathToPose action client for path validation

    Parameters
    ----------
        frame_id (string): Reference frame for navigation, default "map"
        use_local_window (bool): Whether to generate goals within a local window around robot
        local_range_x (float): X-range of local window in meters
        local_range_y (float): Y-range of local window in meters
        max_generate_attempts (int): Maximum attempts for generating valid random poses
        recent_goal_history (int): Number of recent goals to remember and avoid
        idle_time_before_new_goal (float): Seconds to wait between goals
        check_interval (float): Interval in seconds for checking if new goals should be generated
        max_path_length (float): Maximum acceptable path length in meters
        compute_path_timeout (float): Timeout for path computation service
        min_path_length (float): Minimum acceptable path length in meters
        max_dist_home (float): Maximum distance from home before returning

    Services:
        set_home: Sets a new home position if it's reachable from current position

    The node begins by initializing a home position based on the robot's starting location
    and then alternates between random exploration and returning home when necessary.

    """

    def __init__(self):
        super().__init__("roaming_node")
        self.callback_group = ReentrantCallbackGroup()

        # Parámetros configurables
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("use_local_window", True)
        self.declare_parameter("local_range_x", 4.5)
        self.declare_parameter("local_range_y", 4.5)
        self.declare_parameter("max_generate_attempts", 5)
        self.declare_parameter("recent_goal_history", 10)
        self.declare_parameter("idle_time_before_new_goal", 2.0)
        self.declare_parameter("check_interval", 5.0)
        self.declare_parameter("max_path_length", 10.0)
        self.declare_parameter("compute_path_timeout", 5.0)
        self.declare_parameter("min_path_length", 2.0)
        self.declare_parameter("max_dist_home", 8.0)

        # Obtener parámetros
        self.frame_id = self.get_parameter("frame_id").value
        self.use_local_window = self.get_parameter("use_local_window").value
        self.local_range_x = self.get_parameter("local_range_x").value
        self.local_range_y = self.get_parameter("local_range_y").value
        self.max_attempts = int(self.get_parameter("max_generate_attempts").value)
        self.history_size = int(self.get_parameter("recent_goal_history").value)
        self.idle_time = self.get_parameter("idle_time_before_new_goal").value
        self.timer_period = self.get_parameter("check_interval").value
        self.max_path_length = self.get_parameter("max_path_length").value
        self.compute_path_timeout = self.get_parameter("compute_path_timeout").value
        self.min_path_length = self.get_parameter("min_path_length").value
        self.max_dist_home = self.get_parameter("max_dist_home").value
        # Estado
        self.recent_goals = []
        self.goal_active = False
        self.last_goal_end_time = self.get_clock().now()

        # Estado Home
        self.home = None
        self.home_init_timer = self.create_timer(
            0.5, self._init_home, callback_group=self.callback_group
        )
        self.success_nav_count = 0
        self.success_nav_threshold = 5

        # TF2 listener
        self.tf_buffer = Buffer()
        TransformListener(self.tf_buffer, self)

        # Action clients
        self.nav_action_client = ActionClient(
            self, NavigateToPose, "navigate_to_pose", callback_group=self.callback_group
        )
        self.path_action_client = ActionClient(
            self,
            ComputePathToPose,
            "compute_path_to_pose",
            callback_group=self.callback_group,
        )

        # Servicio para fijar Home
        self.create_service(SetHome, "set_home", self.handle_set_home)

    def _init_home(self):
        """Intento de obtener la pose actual: una vez válida, se fija como Home y arranca el roaming."""
        init = self._get_current_pose()
        if init is None:
            return  # sigue intentándolo
        self.home = init
        x = init.pose.position.x
        y = init.pose.position.y
        self.get_logger().info(f"Home inicializado en x={x:.2f}, y={y:.2f}")
        # Cancelar este timer de inicialización
        self.home_init_timer.cancel()
        # Arrancar timer principal de roaming
        self.timer = self.create_timer(
            self.timer_period, self.timer_callback, callback_group=self.callback_group
        )

    def handle_set_home(self, request, response):
        """Servicio que fija la posición de Home si es alcanzable."""
        new_home = request.home
        # Validar con ComputePathToPose
        if not self.path_action_client.wait_for_server(
            timeout_sec=self.compute_path_timeout
        ):
            response.success = False
            response.message = "ComputePathToPose server no disponible."
            return response

        # Construir goal de path desde la posición actual
        start = self._get_current_pose()
        if start is None:
            response.success = False
            response.message = "No se pudo obtener la pose actual."
            return response

        path_goal = ComputePathToPose.Goal()
        path_goal.start = start
        path_goal.goal = new_home

        send = self.path_action_client.send_goal_async(path_goal)
        rclpy.spin_until_future_complete(
            self, send, timeout_sec=self.compute_path_timeout
        )
        if not send.done() or not send.result().accepted:
            response.success = False
            response.message = "Home no es alcanzable (path rechazado)."
            return response
        get_res = send.result().get_result_async()
        rclpy.spin_until_future_complete(
            self, get_res, timeout_sec=self.compute_path_timeout
        )
        if get_res.result().result.path.poses:
            self.home = new_home
            response.success = True
            response.message = "Home configurado correctamente."
        else:
            response.success = False
            response.message = "Home no es alcanzable (sin path)."
        return response

    def _get_current_pose(self):
        """Devuelve PoseStamped de la posición actual en frame_id, o None."""
        try:
            if not self.tf_buffer.can_transform(
                self.frame_id,
                "base_link",
                rclpy.time.Time(),
                timeout=Duration(seconds=self.compute_path_timeout),
            ):
                return None
            trans = self.tf_buffer.lookup_transform(
                self.frame_id,
                "base_link",
                rclpy.time.Time(),
                timeout=Duration(seconds=self.compute_path_timeout),
            )
            ps = PoseStamped()
            ps.header.frame_id = self.frame_id
            ps.header.stamp = self.get_clock().now().to_msg()
            ps.pose.position.x = trans.transform.translation.x
            ps.pose.position.y = trans.transform.translation.y
            ps.pose.position.z = trans.transform.translation.z

            # Orientación
            ps.pose.orientation.x = trans.transform.rotation.x
            ps.pose.orientation.y = trans.transform.rotation.y
            ps.pose.orientation.z = trans.transform.rotation.z
            ps.pose.orientation.w = trans.transform.rotation.w
            return ps
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"Error al obtener pose actual: {e}")
            return None

    def _distance_to(self, pose_stamped):
        """Calcula distancia euclídea entre la pose actual y `pose_stamped`."""
        current = self._get_current_pose()
        if current is None:
            return 0.0
        dx = pose_stamped.pose.position.x - current.pose.position.x
        dy = pose_stamped.pose.position.y - current.pose.position.y
        return math.hypot(dx, dy)

    def timer_callback(self):
        idle = (self.get_clock().now() - self.last_goal_end_time).nanoseconds / 1e9
        if self.goal_active or idle < self.idle_time:
            return

        # Lógica de retorno a Home
        if (
            self.home is not None
            and self.success_nav_count >= self.success_nav_threshold
            and self._distance_to(self.home) >= self.max_dist_home
        ):
            self.get_logger().info("Condición alcanzada: volviendo a Home.")
            goal = NavigateToPose.Goal()
            goal.pose = self.home
            self._send_goal(goal)
            self.success_nav_count = 0
            return

        # Roaming aleatorio
        self.get_logger().info("Generando nueva meta aleatoria...")
        pose = self._generate_valid_random_pose()
        if pose:
            goal = NavigateToPose.Goal()
            goal.pose = pose
            self._send_goal(goal)
        else:
            self.get_logger().warn("No se generó pose válida.")

    def _generate_valid_random_pose(self):
        # Obtener pose actual
        if self.home is not None:
            start = self._get_current_pose()

        for _ in range(self.max_attempts):
            # Generación local o global según parámetro
            if self.use_local_window:
                # Ventana relativa
                min_x = start.pose.position.x - self.local_range_x
                max_x = start.pose.position.x + self.local_range_x
                min_y = start.pose.position.y - self.local_range_y
                max_y = start.pose.position.y + self.local_range_y
            else:
                # Ventana global configurable (mantener min/max originales si
                # se desean)
                min_x = self.get_parameter(
                    "frame_id"
                ).value  # placeholder si se implementa global
                max_x = min_x
                min_y = self.get_parameter("frame_id").value
                max_y = min_y
            x = random.uniform(min_x, max_x)
            y = random.uniform(min_y, max_y)
            yaw = random.uniform(-math.pi, math.pi)

            goal = PoseStamped()
            goal.header.frame_id = self.frame_id
            goal.header.stamp = self.get_clock().now().to_msg()
            goal.pose.position.x = x
            goal.pose.position.y = y
            goal.pose.position.z = 0.0
            q = quaternion_from_euler(0, 0, yaw)
            goal.pose.orientation.x = q[0]
            goal.pose.orientation.y = q[1]
            goal.pose.orientation.z = q[2]
            goal.pose.orientation.w = q[3]

            key = (round(x, 2), round(y, 2))
            if key in self.recent_goals:
                continue

            # Calcular ruta para validar
            if not self.path_action_client.wait_for_server(
                timeout_sec=self.compute_path_timeout
            ):
                self.get_logger().error(
                    "Action server compute_path_to_pose no disponible."
                )
                return None
            path_goal = ComputePathToPose.Goal()

            # calcular ángulo del robot hacia la meta
            dx = goal.pose.position.x - start.pose.position.x
            dy = goal.pose.position.y - start.pose.position.y
            yaw_to_goal = math.atan2(dy, dx)

            # actualizar la orientación del "start" pose
            q = quaternion_from_euler(0, 0, yaw_to_goal)
            start.pose.orientation.x = q[0]
            start.pose.orientation.y = q[1]
            start.pose.orientation.z = q[2]
            start.pose.orientation.w = q[3]

            goal.pose.orientation = start.pose.orientation

            path_goal.start = start
            path_goal.goal = goal
            send_fut = self.path_action_client.send_goal_async(path_goal)
            rclpy.spin_until_future_complete(
                self, send_fut, timeout_sec=self.compute_path_timeout
            )
            if not send_fut.done():
                self.get_logger().warn("Timeout al enviar ComputePathToPose.")
                continue
            handle = send_fut.result()
            if not handle.accepted:
                self.get_logger().warn("ComputePathToPose rechazado.")
                continue
            result_fut = handle.get_result_async()
            rclpy.spin_until_future_complete(
                self, result_fut, timeout_sec=self.compute_path_timeout
            )
            if result_fut.result() is None:
                self.get_logger().warn("ComputePathToPose no devolvió resultado.")
                continue

            result_msg = result_fut.result()
            if not hasattr(result_msg, "result"):
                self.get_logger().warn(
                    'El resultado de ComputePathToPose no contiene un campo "result".'
                )
                continue

            path = result_msg.result.path

            num_segments = len(path.poses)
            self.get_logger().debug(f"Path segments: {num_segments}")
            if num_segments < 2:
                self.get_logger().info("Pose descartada: sin trayectoria válida.")
                continue

            length = 0.0
            for i in range(num_segments - 1):
                dx = path.poses[i + 1].pose.position.x - path.poses[i].pose.position.x
                dy = path.poses[i + 1].pose.position.y - path.poses[i].pose.position.y
                length += math.hypot(dx, dy)

            if length <= self.min_path_length or length > self.max_path_length:
                self.get_logger().info(
                    f"Pose descartada: longitud inválida ({length:.2f}m)"
                )
                continue

            # Aceptar meta válida
            self.recent_goals.append(key)
            if len(self.recent_goals) > self.history_size:
                self.recent_goals.pop(0)
            self.get_logger().info(
                f"Pose aceptada: x={x:.2f}, y={y:.2f}, length={length:.2f}m dentro de ventana local"
            )
            return goal
        return None

    def _send_goal(self, goal_msg):
        if not self.nav_action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Action server navigate_to_pose no disponible.")
            return
        self.goal_active = True
        fut = self.nav_action_client.send_goal_async(
            goal_msg, feedback_callback=self._feedback_callback
        )
        fut.add_done_callback(self._goal_response_callback)

    def _goal_response_callback(self, future):
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error("Meta rechazada.")
            self._reset_goal()
            return
        res_fut = handle.get_result_async()
        res_fut.add_done_callback(self._get_result_callback)

    def _feedback_callback(self, feedback_msg):
        self.get_logger().debug(f"Feedback: {feedback_msg.feedback}")

    def _get_result_callback(self, future):
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info("Meta alcanzada.")
            self.success_nav_count += 1
        else:
            self.get_logger().warn(f"Navegación terminó con estado {status}")
        self._reset_goal()

    def _reset_goal(self):
        self.goal_active = False
        self.last_goal_end_time = self.get_clock().now()


def main(args=None):
    rclpy.init(args=args)
    node = RoamingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Cerrando nodo de roaming...")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
