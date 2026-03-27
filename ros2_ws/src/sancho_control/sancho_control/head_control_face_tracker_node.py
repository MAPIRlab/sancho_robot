#!/usr/bin/env python3
import math

import numpy as np
import rclpy
import tf_transformations
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.msg import State
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import CameraInfo, JointState
from std_msgs.msg import Header

from sancho_interfaces.msg import FaceDetectionArray


class FaceTrackerLifecycle(LifecycleNode):
    """A ROS 2 lifecycle node for tracking faces and controlling a robot's pan-tilt head mechanism."""

    def __init__(self):
        super().__init__("face_tracker_lifecycle")

        # CHANGED: Default topic is now /face_recognitions
        self.declare_parameter("face_topic", "/sancho_perception/human_tracking")
        self.declare_parameter("head_goal_topic", "/head_goal")
        self.declare_parameter("camera_info_topic", "/sancho_camera/camera_info")
        self.declare_parameter("camera_frame", "camera_frame")
        self.declare_parameter("control_rate", 10.0)
        self.declare_parameter("ema_alpha", 0.2)
        self.declare_parameter("p_gain_pan", 0.8)
        self.declare_parameter("p_gain_tilt", 0.8)
        self.declare_parameter("timeout_no_detection", 1.0)
        self.declare_parameter("pan_joint", "pan")
        self.declare_parameter("tilt_joint", "tilt")
        # CHANGED: Removed pan/tilt limit parameters (Hardware node handles this now)

        self.fx = self.fy = self.cx = self.cy = None
        self.camera_info_ready = False

        self.smoothed_u = None
        self.smoothed_v = None
        self.last_detection_time = None
        self.control_timer = None

        self.current_pan = 0.0
        self.current_tilt = 0.0

        self.get_logger().info("FaceTrackerLifecycle creado, esperando configuración.")

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.face_topic = self.get_parameter("face_topic").value
        self.head_goal_topic = self.get_parameter("head_goal_topic").value
        self.camera_info_topic = self.get_parameter("camera_info_topic").value
        self.camera_frame = self.get_parameter("camera_frame").value
        self.control_rate = self.get_parameter("control_rate").value
        self.ema_alpha = self.get_parameter("ema_alpha").value
        self.p_gain_pan = self.get_parameter("p_gain_pan").value
        self.p_gain_tilt = self.get_parameter("p_gain_tilt").value
        self.timeout_no_detection = self.get_parameter("timeout_no_detection").value
        self.pan_joint = self.get_parameter("pan_joint").value
        self.tilt_joint = self.get_parameter("tilt_joint").value

        qos_default = QoSPresetProfiles.SYSTEM_DEFAULT.value

        self.goal_pub = self.create_lifecycle_publisher(
            PoseStamped, self.head_goal_topic, qos_default
        )

        self.get_logger().info("Configurado correctamente.")
        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("--- Entering on_activate ---")
        qos_sensor = QoSPresetProfiles.SENSOR_DATA.value

        try:
            # Subscripción Cámara
            self.camera_info_sub = self.create_subscription(
                CameraInfo, self.camera_info_topic, self.camera_info_callback, qos_sensor
            )
            
            # Subscripción Caras
            self.face_sub = self.create_subscription(
                FaceDetectionArray, self.face_topic, self.face_callback, qos_sensor
            )
            
            # Subscripción Motores
            # CHECK: Ensure this topic is correct and available!
            self.joint_sub = self.create_subscription(
                JointState, "/wxxms/joint_states", self.joint_states_callback, 10
            )

            # Timer
            timer_period = 1.0 / self.control_rate
            self.control_timer = self.create_timer(timer_period, self.control_loop)

            self.get_logger().info("--- Activation Successful ---")
            return TransitionCallbackReturn.SUCCESS

        except Exception as e:
            # This will print the exact error to your console
            self.get_logger().error(f"CRITICAL ERROR DURING ACTIVATION: {e}")
            import traceback
            self.get_logger().error(traceback.format_exc())
            return TransitionCallbackReturn.FAILURE

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.destroy_timer(self.control_timer)
        self.destroy_subscription(self.camera_info_sub)
        self.destroy_subscription(self.face_sub)
        self.destroy_subscription(self.joint_sub)

        self.get_logger().info("Nodo desactivado.")
        return super().on_deactivate(state)


    def joint_states_callback(self, msg: JointState):
        try:
            idx_pan = msg.name.index(self.pan_joint)
            idx_tilt = msg.name.index(self.tilt_joint)
            self.current_pan = msg.position[idx_pan]
            self.current_tilt = msg.position[idx_tilt]
        except ValueError:
            pass

    def camera_info_callback(self, msg: CameraInfo):
        if not self.camera_info_ready:
            self.fx, self.fy = msg.k[0], msg.k[4]
            self.cx, self.cy = msg.k[2], msg.k[5]
            self.camera_info_ready = True
            self.get_logger().info(f"+++ Camera Info Initialized: cx={self.cx}, cy={self.cy}, fx={self.fx}")

    def face_callback(self, msg: FaceDetectionArray):
        # FIX: Using precise float time instead of integer seconds
        now = self.get_clock().now().nanoseconds / 1e9
        
        if not msg.detections:
            return

        if not self.camera_info_ready:
            # This is a common failure point
            self.get_logger().warn("Received face detection but CameraInfo is not ready yet!", throttle_duration_sec=2.0)
            return

        # Pick best face
        best = max(msg.detections, key=lambda f: f.confidence)
        u = best.corner.x + best.width / 2.0
        v = best.corner.y + best.height / 2.0

        alpha = self.ema_alpha
        self.smoothed_u = (
            u if self.smoothed_u is None else alpha * u + (1 - alpha) * self.smoothed_u
        )
        self.smoothed_v = (
            v if self.smoothed_v is None else alpha * v + (1 - alpha) * self.smoothed_v
        )
        self.last_detection_time = now
        
        # DEBUG: Confirming tracking is "alive"
        self.get_logger().info(f"Tracking face at pixels ({u:.1f}, {v:.1f}) -> Smoothed: ({self.smoothed_u:.1f}, {self.smoothed_v:.1f})", throttle_duration_sec=1.0)

    def control_loop(self):
        # FIX: Using precise float time
        now = self.get_clock().now().nanoseconds / 1e9
        
        if self.smoothed_u is None:
            # We haven't seen a face yet
            return

        if self.last_detection_time is None:
            return

        time_diff = now - self.last_detection_time
        if time_diff > self.timeout_no_detection:
            self.get_logger().warn(f"Tracking Timeout! No detection for {time_diff:.2f}s", throttle_duration_sec=2.0)
            return

        err_x = self.smoothed_u - self.cx
        err_y = self.smoothed_v - self.cy

        delta_pan = -math.atan2(err_x, self.fx)
        delta_tilt = math.atan2(err_y, self.fy)

        pan_cmd = self.current_pan + self.p_gain_pan * delta_pan
        tilt_cmd = self.current_tilt + self.p_gain_tilt * delta_tilt

        msg = PoseStamped()
        msg.header = Header(
            stamp=self.get_clock().now().to_msg(), 
            frame_id=self.camera_frame
        )
        q = tf_transformations.quaternion_from_euler(0, tilt_cmd, pan_cmd)
        (
            msg.pose.orientation.x,
            msg.pose.orientation.y,
            msg.pose.orientation.z,
            msg.pose.orientation.w,
        ) = q

        self.goal_pub.publish(msg)
        # FINAL DEBUG: Success check
        self.get_logger().info(f"PUBLISHED Goal: Pan={pan_cmd:.2f}, Tilt={tilt_cmd:.2f}", throttle_duration_sec=1.0)


def main(args=None):
    try:
        rclpy.init(args=args)
        node = FaceTrackerLifecycle()
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    except Exception as e:
        node.get_logger().error(f"Exception in node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()