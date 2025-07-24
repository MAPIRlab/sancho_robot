#!/usr/bin/env python3

import random
from enum import Enum

import rclpy
import tf_transformations
from geometry_msgs.msg import PoseStamped
from interbotix_xs_msgs.msg import JointGroupCommand
from interbotix_xs_msgs.srv import OperatingModes
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import JointState


class State(Enum):
    IDLE = 0
    TRACKING = 1


class HRIHeadNode(Node):
    """ROS 2 node to control the robot's head for Human-Robot Interaction.

    This node provides functionality to move the robot head in pan and tilt
    motions. It operates in two main states:
    - IDLE: performs random movements within specified limits
    - TRACKING: moves the head to track a specific target

    The node accepts PoseStamped messages with orientation (as quaternion)
    that get converted to pan and tilt angles. It also provides timeout
    functionality to return to idle state when tracking is no longer active.

    Parameters
    ----------
    idle_move_min_interval : float
        Minimum interval (seconds) between random movements in idle state
    idle_move_max_interval : float
        Maximum interval (seconds) between random movements in idle state
    pan_limit : list
        Min and max values for pan motion [min, max]
    tilt_limit : list
        Min and max values for tilt motion [min, max]
    tolerance : float
        Angular tolerance to consider a target reached
    tracking_timeout : float
        Seconds to wait before returning to idle when no new targets received
    joint_group_name : str
        Name of the joint group for control commands
    pan_joint : str
        Name of the pan joint in the robot
    tilt_joint : str
        Name of the tilt joint in the robot
    tracking_topic : str
        Topic name for receiving target poses to track

    Published Topics:
    ---------------
    /wxxms/commands/joint_group (JointGroupCommand)
        Commands to control joint positions

    Subscribed Topics:
    ---------------
    /wxxms/joint_states (JointState)
        Current state of the robot joints
    [tracking_topic] (PoseStamped)
        Target pose for the robot head to track

    Services:
    --------
    /wxxms/set_operating_modes (OperatingModes)
        Service to set joint operating modes

    """

    def __init__(self):
        super().__init__("hri_head_node")

        # Parámetros
        self.declare_parameter("idle_move_min_interval", 5.0)
        self.declare_parameter("idle_move_max_interval", 8.0)
        self.declare_parameter("pan_limit", [-1.20, 1.20])
        self.declare_parameter("tilt_limit", [-0.5, 0.0])
        self.declare_parameter("tolerance", 0.001)
        self.declare_parameter("tracking_timeout", 5.0)
        self.declare_parameter("joint_group_name", "turret")
        self.declare_parameter("pan_joint", "pan")
        self.declare_parameter("tilt_joint", "tilt")
        self.declare_parameter("tracking_topic", "/head_goal")

        self.idle_min = self.get_parameter("idle_move_min_interval").value
        self.idle_max = self.get_parameter("idle_move_max_interval").value
        pan_limits = self.get_parameter("pan_limit").value
        self.pan_min, self.pan_max = pan_limits
        tilt_limits = self.get_parameter("tilt_limit").value
        self.tilt_min, self.tilt_max = tilt_limits
        self.tolerance = self.get_parameter("tolerance").value
        self.tracking_timeout = self.get_parameter("tracking_timeout").value
        self.joint_group = self.get_parameter("joint_group_name").value
        self.pan_joint = self.get_parameter("pan_joint").value
        self.tilt_joint = self.get_parameter("tilt_joint").value
        tracking_topic = self.get_parameter("tracking_topic").value

        # Variables de estado
        self.state = State.IDLE
        self.last_idle_move_time = self.get_clock().now()
        self.next_idle_delay = random.uniform(self.idle_min, self.idle_max)
        self.tracking_timer = None

        # Publishers & Subscribers
        qos = QoSProfile(depth=10)
        self.joint_pub = self.create_publisher(
            JointGroupCommand, "/wxxms/commands/joint_group", qos
        )
        self.joint_state_sub = self.create_subscription(
            JointState, "/wxxms/joint_states", self.joint_state_cb, qos
        )
        self.goal_sub = self.create_subscription(
            PoseStamped, tracking_topic, self.goal_cb, qos
        )

        # Servicio de modo operativo
        self.op_srv = self.create_client(OperatingModes, "/wxxms/set_operating_modes")
        while not self.op_srv.wait_for_service(timeout_sec=1.0):
            self.get_logger().warning("Waiting for OperatingModes service...")
        self.set_position_control_mode()

        # Timer principal
        self.timer = self.create_timer(0.1, self.update)
        self.move_head(0.0, 0.0)
        self.get_logger().info(
            "HRI Head node initialized with PoseStamped goal interface."
        )

    def set_position_control_mode(self):
        req = OperatingModes.Request()
        req.cmd_type = "group"
        req.name = self.joint_group
        req.mode = "position"
        req.profile_type = "time"
        req.profile_velocity = 2400  # Tiempo que tarda en llegar a la posición
        req.profile_acceleration = (
            300  # TIempo que tarda en llegar a la aceleración maxima
        )
        future = self.op_srv.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is None:
            self.get_logger().error("Failed to set operating mode.")
        else:
            self.get_logger().info("Operating mode set to POSITION.")

    def joint_state_cb(self, msg: JointState):
        try:
            idx_pan = msg.name.index(self.pan_joint)
            idx_tilt = msg.name.index(self.tilt_joint)
        except ValueError:
            return
        self.current_pan = msg.position[idx_pan]
        self.current_tilt = msg.position[idx_tilt]

    def goal_cb(self, msg: PoseStamped):
        # Extraer yaw/pan y pitch/tilt
        q = msg.pose.orientation
        roll, pitch, yaw = tf_transformations.euler_from_quaternion(
            [q.x, q.y, q.z, q.w]
        )
        target_pan = yaw  # ← invertir si gira al revés
        target_tilt = pitch  # ← invertir si se inclina al revés

        # Si aún no hemos recibido nunca joint_states, movemos de todas formas
        if hasattr(self, "current_pan") and hasattr(self, "current_tilt"):
            dp = abs(target_pan - self.current_pan)
            dt = abs(target_tilt - self.current_tilt)
            if dp <= self.tolerance and dt <= self.tolerance:
                self.get_logger().info(
                    f"Target within tolerance ±{self.tolerance:.2f} (Δpan={dp:.2f}, Δtilt={dt:.2f}), not moving."
                )
                return

        self.get_logger().info(
            f"Received PoseStamped goal ▶ pan={target_pan:.2f}, tilt={target_tilt:.2f}"
        )
        self.move_head(target_pan, target_tilt)
        self.state = State.TRACKING

        # Resetear timeout de tracking
        if self.tracking_timer:
            self.tracking_timer.cancel()
        self.tracking_timer = self.create_timer(
            self.tracking_timeout, self.tracking_timeout_cb
        )

    def tracking_timeout_cb(self):
        self.get_logger().info("Tracking timeout reached. Returning to idle.")
        self.state = State.IDLE
        self.last_idle_move_time = self.get_clock().now()
        self.next_idle_delay = random.uniform(self.idle_min, self.idle_max)
        if self.tracking_timer:
            self.tracking_timer.cancel()
            self.tracking_timer = None

    def move_head(self, pan: float, tilt: float):
        cmd = JointGroupCommand()
        cmd.name = self.joint_group
        cmd.cmd = [float(pan), float(tilt)]
        self.joint_pub.publish(cmd)
        self.get_logger().debug(f"Publishing head command: [{pan:.2f}, {tilt:.2f}]")

    def update(self):
        now = self.get_clock().now()
        if self.state == State.IDLE:
            elapsed = (now - self.last_idle_move_time).nanoseconds * 1e-9
            if elapsed >= self.next_idle_delay:
                rand_pan = random.uniform(self.pan_min, self.pan_max)
                rand_tilt = random.uniform(self.tilt_min, self.tilt_max)
                self.get_logger().info(
                    f"Idle move ▶ pan={rand_pan:.2f}, tilt={rand_tilt:.2f}"
                )
                self.move_head(rand_pan, rand_tilt)
                self.last_idle_move_time = now
                self.next_idle_delay = random.uniform(self.idle_min, self.idle_max)


def main(args=None):
    rclpy.init(args=args)
    node = HRIHeadNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
