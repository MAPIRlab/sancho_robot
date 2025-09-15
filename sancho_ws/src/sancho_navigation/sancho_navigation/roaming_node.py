#!/usr/bin/env python3

import math
import random

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.duration import Duration
from rclpy.time import Time
from rclpy.executors import MultiThreadedExecutor

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose, NavigateToPose

from tf2_ros import Buffer, TransformListener, LookupException, ConnectivityException, ExtrapolationException
from tf_transformations import quaternion_from_euler

from sancho_msgs.srv import SetHome


class RoamingNode(Node):
    def __init__(self):
        super().__init__("roaming_node")
        self.callback_group = ReentrantCallbackGroup()

        # Parámetros configurables
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("robot_frame_id", "base_footprint")
        self.declare_parameter("use_local_window", True)
        self.declare_parameter("local_range_x", 4.5)
        self.declare_parameter("local_range_y", 4.5)
        self.declare_parameter("global_min_x", -10.0)
        self.declare_parameter("global_max_x", 10.0)
        self.declare_parameter("global_min_y", -10.0)
        self.declare_parameter("global_max_y", 10.0)
        self.declare_parameter("max_generate_attempts", 5)
        self.declare_parameter("recent_goal_history", 10)
        self.declare_parameter("idle_time_before_new_goal", 2.0)
        self.declare_parameter("check_interval", 5.0)
        self.declare_parameter("max_path_length", 10.0)
        self.declare_parameter("min_path_length", 2.0)
        self.declare_parameter("compute_path_timeout", 5.0)
        self.declare_parameter("navigate_timeout", 120.0)
        self.declare_parameter("max_dist_home", 8.0)
        self.declare_parameter("safe_margin", 0.30)  # evita metas demasiado cerca de obstáculos/ límites

        # Obtener parámetros
        self.frame_id = self.get_parameter("frame_id").value
        self.robot_frame_id = self.get_parameter("robot_frame_id").value
        self.use_local_window = self.get_parameter("use_local_window").value
        self.local_range_x = float(self.get_parameter("local_range_x").value)
        self.local_range_y = float(self.get_parameter("local_range_y").value)
        self.global_min_x = float(self.get_parameter("global_min_x").value)
        self.global_max_x = float(self.get_parameter("global_max_x").value)
        self.global_min_y = float(self.get_parameter("global_min_y").value)
        self.global_max_y = float(self.get_parameter("global_max_y").value)
        self.max_attempts = int(self.get_parameter("max_generate_attempts").value)
        self.history_size = int(self.get_parameter("recent_goal_history").value)
        self.idle_time = float(self.get_parameter("idle_time_before_new_goal").value)
        self.timer_period = float(self.get_parameter("check_interval").value)
        self.max_path_length = float(self.get_parameter("max_path_length").value)
        self.min_path_length = float(self.get_parameter("min_path_length").value)
        self.compute_path_timeout = float(self.get_parameter("compute_path_timeout").value)
        self.navigate_timeout = float(self.get_parameter("navigate_timeout").value)
        self.max_dist_home = float(self.get_parameter("max_dist_home").value)
        self.safe_margin = float(self.get_parameter("safe_margin").value)

        # Estado
        self.recent_goals = []  # lista de tuplas (x_round, y_round)
        self.goal_active = False
        self.last_goal_end_time = self.get_clock().now()

        # Estado Home
        self.home = None
        self.success_nav_count = 0
        self.success_nav_threshold = 5

        # TF2 listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Action clients
        self.nav_action_client = ActionClient(self, NavigateToPose, "navigate_to_pose", callback_group=self.callback_group)
        self.path_action_client = ActionClient(self, ComputePathToPose, "compute_path_to_pose", callback_group=self.callback_group)

        # Servicio para fijar Home
        self.create_service(SetHome, "set_home", self.handle_set_home)

        # Timer de inicialización de Home
        self.home_init_timer = self.create_timer(0.5, self._init_home, callback_group=self.callback_group)

        self.get_logger().info("RoamingNode inicializado; esperando TF para fijar Home…")

    # -------------------- Utilidades --------------------
    def _init_home(self):
        """Obtiene la pose actual; una vez válida, la fija como Home y arranca el timer principal."""
        init = self._get_current_pose()
        if init is None:
            return
        self.home = init
        self.get_logger().info(f"Home inicializado en x={init.pose.position.x:.2f}, y={init.pose.position.y:.2f}")
        self.home_init_timer.cancel()
        # Arranca timer principal de roaming
        self.timer = self.create_timer(self.timer_period, self.timer_callback, callback_group=self.callback_group)

    def _get_current_pose(self) -> PoseStamped | None:
        """Devuelve PoseStamped en self.frame_id o None si TF no está disponible."""
        
        try:
            if not self.tf_buffer.can_transform(self.frame_id, self.robot_frame_id, Time(), timeout=Duration(seconds=self.compute_path_timeout)):
                self.get_logger().warn(f"No se puede obtener la transformacion de {self.frame_id} a {self.robot_frame_id}")
                return None
            trans = self.tf_buffer.lookup_transform(self.frame_id, self.robot_frame_id, Time(), timeout=Duration(seconds=self.compute_path_timeout))
        except (LookupException, ConnectivityException, ExtrapolationException) as e:
            self.get_logger().warn(f"Error TF al obtener pose actual: {e}")
            return None

        ps = PoseStamped()
        ps.header.frame_id = self.frame_id
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose.position.x = trans.transform.translation.x
        ps.pose.position.y = trans.transform.translation.y
        ps.pose.position.z = trans.transform.translation.z
        ps.pose.orientation = trans.transform.rotation
        return ps

    def _distance_to(self, pose_stamped: PoseStamped) -> float:
        current = self._get_current_pose()
        if current is None:
            return 0.0
        dx = pose_stamped.pose.position.x - current.pose.position.x
        dy = pose_stamped.pose.position.y - current.pose.position.y
        return math.hypot(dx, dy)

    # -------------------- Servicio --------------------
    def handle_set_home(self, request, response):
        """Fija Home si es alcanzable desde la pose actual."""
        new_home: PoseStamped = request.home
        if new_home.header.frame_id and new_home.header.frame_id != self.frame_id:
            response.success = False
            response.message = f"El frame de Home '{new_home.header.frame_id}' no coincide con '{self.frame_id}'."
            return response

        if not self.path_action_client.wait_for_server(timeout_sec=self.compute_path_timeout):
            response.success = False
            response.message = "ComputePathToPose server no disponible."
            return response

        start = self._get_current_pose()
        if start is None:
            response.success = False
            response.message = "No se pudo obtener la pose actual."
            return response

        goal_msg = ComputePathToPose.Goal()
        goal_msg.start = start
        goal_msg.goal = new_home

        send = self.path_action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send, timeout_sec=self.compute_path_timeout)
        if not send.done():
            response.success = False
            response.message = "Timeout al enviar ComputePathToPose."
            return response
        handle = send.result()
        if not handle.accepted:
            response.success = False
            response.message = "Home no es alcanzable (goal rechazado)."
            return response

        get_res = handle.get_result_async()
        rclpy.spin_until_future_complete(self, get_res, timeout_sec=self.compute_path_timeout)
        if not get_res.done() or get_res.result() is None:
            response.success = False
            response.message = "Timeout/resultado vacío de ComputePathToPose."
            return response

        result = get_res.result()
        path = getattr(result.result, "path", None)
        if path and path.poses:
            self.home = new_home
            response.success = True
            response.message = "Home configurado correctamente."
        else:
            response.success = False
            response.message = "Home no es alcanzable (sin path)."
        return response

    # -------------------- Roaming --------------------
    def timer_callback(self):
        self.get_logger().warn("11")

        idle = (self.get_clock().now() - self.last_goal_end_time).nanoseconds / 1e9
        if self.goal_active or idle < self.idle_time:
            return

        # Volver a Home si procede
        if self.home is not None and self.success_nav_count >= self.success_nav_threshold and self._distance_to(self.home) >= self.max_dist_home:
            self.get_logger().info("Condición alcanzada: volviendo a Home.")
            goal = NavigateToPose.Goal()
            goal.pose = self.home
            self._send_goal(goal)
            self.success_nav_count = 0
            return

        # Generar meta aleatoria válida
        self.get_logger().info("Generando nueva meta aleatoria…")
        pose = self._generate_valid_random_pose()
        if pose is None:
            self.get_logger().warn("No se pudo generar una pose válida.")
            return
        goal = NavigateToPose.Goal()
        goal.pose = pose
        self._send_goal(goal)

    def _generate_valid_random_pose(self) -> PoseStamped | None:
        start = self._get_current_pose()
        if start is None:
            self.get_logger().warn("No hay pose actual (TF). Reintentando más tarde.")
            return None

        # Espera a servidor de ComputePathToPose una sola vez
        if not self.path_action_client.wait_for_server(timeout_sec=self.compute_path_timeout):
            self.get_logger().error("Action server 'compute_path_to_pose' no disponible.")
            return None

        for _ in range(self.max_attempts):
            if self.use_local_window:
                min_x = start.pose.position.x - self.local_range_x
                max_x = start.pose.position.x + self.local_range_x
                min_y = start.pose.position.y - self.local_range_y
                max_y = start.pose.position.y + self.local_range_y
            else:
                min_x = self.global_min_x
                max_x = self.global_max_x
                min_y = self.global_min_y
                max_y = self.global_max_y

            # Margen de seguridad (evita puntos en los bordes exactos)
            min_x += self.safe_margin
            max_x -= self.safe_margin
            min_y += self.safe_margin
            max_y -= self.safe_margin
            if min_x >= max_x or min_y >= max_y:
                self.get_logger().error("Rangos de ventana inválidos; revise parámetros.")
                return None

            x = random.uniform(min_x, max_x)
            y = random.uniform(min_y, max_y)

            # Orienta el objetivo mirando desde 'start' hacia el punto (x,y)
            dx = x - start.pose.position.x
            dy = y - start.pose.position.y
            yaw_to_goal = math.atan2(dy, dx)
            q = quaternion_from_euler(0.0, 0.0, yaw_to_goal)

            goal = PoseStamped()
            goal.header.frame_id = self.frame_id
            goal.header.stamp = self.get_clock().now().to_msg()
            goal.pose.position.x = x
            goal.pose.position.y = y
            goal.pose.position.z = 0.0
            goal.pose.orientation.x = q[0]
            goal.pose.orientation.y = q[1]
            goal.pose.orientation.z = q[2]
            goal.pose.orientation.w = q[3]

            key = (round(x, 2), round(y, 2))
            if key in self.recent_goals:
                self.get_logger().debug("Meta descartada por historial reciente.")
                continue

            # Validación de ruta
            path_goal = ComputePathToPose.Goal()
            path_goal.start = start
            path_goal.goal = goal

            send_fut = self.path_action_client.send_goal_async(path_goal)
            rclpy.spin_until_future_complete(self, send_fut, timeout_sec=self.compute_path_timeout)
            if not send_fut.done():
                self.get_logger().warn("Timeout al enviar ComputePathToPose.")
                continue
            handle = send_fut.result()
            if not handle.accepted:
                self.get_logger().debug("ComputePathToPose rechazado por el servidor.")
                continue

            result_fut = handle.get_result_async()
            rclpy.spin_until_future_complete(self, result_fut, timeout_sec=self.compute_path_timeout)
            if not result_fut.done() or result_fut.result() is None:
                self.get_logger().warn("ComputePathToPose no devolvió resultado (timeout / None).")
                continue

            result_msg = result_fut.result()
            if not hasattr(result_msg, "result") or not hasattr(result_msg.result, "path"):
                self.get_logger().warn("Resultado de ComputePathToPose sin 'result.path'.")
                continue

            path = result_msg.result.path
            if not path.poses or len(path.poses) < 2:
                self.get_logger().info("Pose descartada: sin trayectoria válida.")
                continue

            # Calcular longitud aproximada de la ruta
            length = 0.0
            for i in range(len(path.poses) - 1):
                dx = path.poses[i + 1].pose.position.x - path.poses[i].pose.position.x
                dy = path.poses[i + 1].pose.position.y - path.poses[i].pose.position.y
                length += math.hypot(dx, dy)

            if length <= self.min_path_length or length > self.max_path_length:
                self.get_logger().info(f"Pose descartada: longitud inválida ({length:.2f} m)")
                continue

            # Aceptar meta válida
            self.recent_goals.append(key)
            if len(self.recent_goals) > self.history_size:
                self.recent_goals.pop(0)
            self.get_logger().info(f"Pose aceptada: x={x:.2f}, y={y:.2f}, length={length:.2f} m")
            return goal

        return None

    # -------------------- Navegación --------------------
    def _send_goal(self, goal_msg: NavigateToPose.Goal):
        if not self.nav_action_client.wait_for_server(timeout_sec=self.compute_path_timeout):
            self.get_logger().error("Action server 'navigate_to_pose' no disponible.")
            return
        self.get_logger().warn("22")

        self.goal_active = True
        fut = self.nav_action_client.send_goal_async(goal_msg, feedback_callback=self._feedback_callback)
        fut.add_done_callback(self._goal_response_callback)
        return

    def _goal_response_callback(self, future):
        handle = future.result()
        if not handle or not handle.accepted:
            self.get_logger().error("Meta de navegación rechazada.")
            self._reset_goal()
            return
        res_fut = handle.get_result_async()
        res_fut.add_done_callback(self._get_result_callback)

    def _feedback_callback(self, feedback_msg):
        self.get_logger().info(f"Feedback: {feedback_msg.feedback}")

    def _get_result_callback(self, future):
        result = future.result()
        status = getattr(result, "status", None)
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
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("Cerrando nodo de roaming…")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
