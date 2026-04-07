#!/usr/bin/env python3
"""Nodo de ROS2 (Humble) mejorado para roaming aleatorio del robot usando Nav2.
Incluye validación de path mediante acción ComputePathToPose y generación de objetivos
relativos a la posición actual dentro de una ventana local.
"""
import math
import random

import rclpy
from rclpy.executors import MultiThreadedExecutor

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

from sancho_interfaces.srv import SetHome


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

        self.generating = False
        self._gen_attempt_idx = 0
        self._gen_start_pose = None  # pose inicial cacheada para esta tanda
        self.get_logger().info("Iniciando roaming node")

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
        """Servicio que asíncronamente valida y fija la posición de Home."""
        new_home = request.home
        if not self.path_action_client.wait_for_server(timeout_sec=0.2):
            response.success = False
            response.message = "ComputePathToPose server no disponible."
            return response

        start = self._get_current_pose()
        if start is None:
            response.success = False
            response.message = "No se pudo obtener la pose actual."
            return response

        path_goal = ComputePathToPose.Goal()
        path_goal.start = start
        path_goal.goal = new_home

        send_future = self.path_action_client.send_goal_async(path_goal)
        send_future.add_done_callback(
            lambda fut: self._on_home_path_goal_sent(fut, new_home)
        )

        response.success = True
        response.message = "Validación de ruta iniciada asíncronamente."
        return response

    def _on_home_path_goal_sent(self, future, new_home):
        try:
            handle = future.result()
        except Exception as e:
            self.get_logger().warn(f"Set Home: Error de Future: {e}")
            return
            
        if not handle or not handle.accepted:
            self.get_logger().warn("Set Home: Path rechazado, meta ignorada.")
            return

        result_future = handle.get_result_async()
        result_future.add_done_callback(
            lambda fut: self._on_home_path_result(fut, new_home)
        )

    def _on_home_path_result(self, future, new_home):
        try:
            result_msg = future.result()
        except Exception:
            self.get_logger().warn("Set Home: Validación de ruta fallida.")
            return
            
        if not result_msg or not hasattr(result_msg, "result"):
            self.get_logger().warn("Set Home: Falló validación de ruta (sin resultado).")
            return
            
        path = result_msg.result.path
        if len(path.poses) >= 2:
            self.home = new_home
            self.get_logger().info("Set Home: Validado y fijado correctamente.")
        else:
            self.get_logger().warn("Set Home: Meta inalcanzable, descartado.")

    def _get_current_pose(self):
        """Devuelve PoseStamped de la posición actual en frame_id, o None."""
        try:
            if not self.tf_buffer.can_transform(
                self.frame_id,
                "base_link",
                rclpy.time.Time(),
                timeout=Duration(seconds=self.compute_path_timeout),
            ):
                raise LookupException(f"Transform no disponible: {self.frame_id} <- base_link")
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
        if self.goal_active  or self.generating or idle < self.idle_time:
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
        self._start_async_random_pose_generation()

        # Se invoca la generación asíncrona validada, descartando métodos sincrónicos.

    def _start_async_random_pose_generation(self):
        """Arranca una tanda de intentos asíncronos de validación de path."""
        start = self._get_current_pose()
        if start is None:
            self.get_logger().warn("No hay pose actual; no se puede generar candidatos.")
            return
        self.generating = True
        self._gen_attempt_idx = 0
        self._gen_start_pose = start
        self._try_next_candidate()

    def _try_next_candidate(self):
        """Genera un candidato y lanza ComputePathToPose de forma asíncrona."""
        if self._gen_attempt_idx >= self.max_attempts:
            self.get_logger().warn("No se generó pose válida (se agotaron intentos).")
            self.generating = False
            return

        # Generación local (o global futura)
        start = self._gen_start_pose
        if start is None:
            self.generating = False
            return

        if self.use_local_window:
            min_x = start.pose.position.x - self.local_range_x
            max_x = start.pose.position.x + self.local_range_x
            min_y = start.pose.position.y - self.local_range_y
            max_y = start.pose.position.y + self.local_range_y
        else:
            # Placeholder si se implementa ventana global configurable
            min_x = start.pose.position.x - 10.0
            max_x = start.pose.position.x + 10.0
            min_y = start.pose.position.y - 10.0
            max_y = start.pose.position.y + 10.0

        x = random.uniform(min_x, max_x)
        y = random.uniform(min_y, max_y)
        yaw = random.uniform(-math.pi, math.pi)

        candidate = PoseStamped()
        candidate.header.frame_id = self.frame_id
        candidate.header.stamp = self.get_clock().now().to_msg()
        candidate.pose.position.x = x
        candidate.pose.position.y = y
        candidate.pose.position.z = 0.0
        q = quaternion_from_euler(0, 0, yaw)
        candidate.pose.orientation.x = q[0]
        candidate.pose.orientation.y = q[1]
        candidate.pose.orientation.z = q[2]
        candidate.pose.orientation.w = q[3]

        key = (round(x, 2), round(y, 2))
        if key in self.recent_goals:
            self.get_logger().debug("Candidato repetido (historial); probando otro...")
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        if not self.path_action_client.wait_for_server(timeout_sec=0.2):
            self.get_logger().error("Action server compute_path_to_pose no disponible.")
            self.generating = False
            return

        # Ajustar orientación del start hacia la meta para facilitar el planner
        dx = candidate.pose.position.x - start.pose.position.x
        dy = candidate.pose.position.y - start.pose.position.y
        yaw_to_goal = math.atan2(dy, dx)
        q_start = quaternion_from_euler(0, 0, yaw_to_goal)
        start_oriented = PoseStamped()
        start_oriented.header = start.header
        start_oriented.pose = start.pose
        start_oriented.pose.orientation.x = q_start[0]
        start_oriented.pose.orientation.y = q_start[1]
        start_oriented.pose.orientation.z = q_start[2]
        start_oriented.pose.orientation.w = q_start[3]

        # Alinear yaw destino con rumbo de partida (opcional)
        candidate.pose.orientation = start_oriented.pose.orientation

        path_goal = ComputePathToPose.Goal()
        path_goal.start = start_oriented
        path_goal.goal = candidate

        self.get_logger().debug(
            f"Intento {self._gen_attempt_idx + 1}/{self.max_attempts}: "
            f"x={x:.2f}, y={y:.2f}"
        )

        send_future = self.path_action_client.send_goal_async(path_goal)

        # Encadenar callback cuando el envío termina
        send_future.add_done_callback(
            lambda fut, cand=candidate, key=key: self._on_path_goal_sent(fut, cand, key)
        )
        
    def _on_path_goal_sent(self, future, candidate: PoseStamped, key):
        """Callback al terminar send_goal_async para ComputePathToPose."""
        try:
            handle = future.result()
        except Exception as e:
            self.get_logger().warn(f"Fallo al enviar ComputePathToPose: {e}")
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        if not handle or not handle.accepted:
            self.get_logger().debug("ComputePathToPose rechazado; probando otro candidato.")
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        # Obtener el resultado de la acción (también asíncrono)
        result_future = handle.get_result_async()
        result_future.add_done_callback(
            lambda fut, cand=candidate, key=key: self._on_path_result(fut, cand, key)
        )

    def _on_path_result(self, future, candidate: PoseStamped, key):
        """Callback de get_result_async: valida longitud del path y decide."""
        try:
            result_msg = future.result()
        except Exception as e:
            self.get_logger().warn(f"Error al obtener resultado del path: {e}")
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        if not result_msg or not hasattr(result_msg, "result"):
            self.get_logger().warn("Resultado de ComputePathToPose inválido.")
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        path = result_msg.result.path
        num_segments = len(path.poses)
        if num_segments < 2:
            self.get_logger().info("Pose descartada: sin trayectoria válida.")
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        length = self._compute_path_length(path)
        self.get_logger().debug(f"Longitud de path: {length:.2f} m")

        if length <= self.min_path_length or length > self.max_path_length:
            self.get_logger().info(
                f"Pose descartada: longitud inválida ({length:.2f} m)"
            )
            self._gen_attempt_idx += 1
            self._try_next_candidate()
            return

        # ---> ACEPTADA <---
        self.recent_goals.append(key)
        if len(self.recent_goals) > self.history_size:
            self.recent_goals.pop(0)
        self.get_logger().info(
            f"Pose aceptada: x={candidate.pose.position.x:.2f}, "
            f"y={candidate.pose.position.y:.2f}, length={length:.2f} m"
        )
        self.generating = False  # cerrar tanda

        goal = NavigateToPose.Goal()
        goal.pose = candidate
        self._send_goal(goal)  # recién ahora se navega
        
    @staticmethod
    def _compute_path_length(path_msg):
        """Suma de distancias euclídeas entre poses consecutivas."""
        length = 0.0
        poses = path_msg.poses
        for i in range(len(poses) - 1):
            dx = poses[i + 1].pose.position.x - poses[i].pose.position.x
            dy = poses[i + 1].pose.position.y - poses[i].pose.position.y
            length += math.hypot(dx, dy)
        return length



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
        executor = MultiThreadedExecutor(num_threads=4)  # 2–4 hilos va bien
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("Cerrando nodo de roaming...")
    finally:
        node.destroy_node()
        rclpy.shutdown()
if __name__ == "__main__":
    main()
