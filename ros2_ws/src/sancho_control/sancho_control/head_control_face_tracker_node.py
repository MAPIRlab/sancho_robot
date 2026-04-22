#!/usr/bin/env python3
import math
import rclpy
import tf_transformations
from geometry_msgs.msg import PoseStamped
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import CameraInfo, JointState
from std_msgs.msg import Header, String

from sancho_interfaces.msg import FaceRecognitionArray

class FaceTrackerLifecycle(LifecycleNode):
    """
    ROS 2 lifecycle node for tracking a SPECIFIC face based on its ID 
    and controlling a robot's pan-tilt head mechanism using a PID controller.
    """

    def __init__(self):
        super().__init__("face_tracker_lifecycle")
        self._declare_all_parameters()
        self._initialize_state_variables()
        self.get_logger().info("FaceTrackerLifecycle initialized. Waiting for on_configure().")

    def _declare_all_parameters(self):
        """Groups all parameter declarations for a cleaner constructor."""
        # Topics
        self.declare_parameter("face_topic", "/face_recognitions")
        self.declare_parameter("head_goal_topic", "/head_goal")
        self.declare_parameter("camera_info_topic", "/sancho_camera/camera_info")
        self.declare_parameter("target_topic", "/face_tracker/set_target")
        
        # Node settings
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("control_rate", 20.0)
        self.declare_parameter("ema_alpha", 0.25)
        self.declare_parameter("timeout_no_detection", 2.0)
        
        # Hardware
        self.declare_parameter("pan_joint", "pan")
        self.declare_parameter("tilt_joint", "tilt")
        
        # Control parameters
        self.declare_parameter("p_gain_pan", 0.6)
        self.declare_parameter("p_gain_tilt", 1.0)

    def _initialize_state_variables(self):
        """Initializes all internal tracking and state variables."""
        self.is_tracking_active = False
        self.target_id = None
        
        # Camera intrinsics
        self.fx = self.fy = self.cx = self.cy = None
        self.camera_info_ready = False

        # Tracking state
        self.smoothed_pixel_x = None
        self.smoothed_pixel_y = None
        self.last_detection_time = None
        self.last_control_time = None
        self.new_detection_ready = False

        # Robot hardware state
        self.current_pan = 0.0
        self.current_tilt = 0.0

    # --- Lifecycle Transitions ---

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        # Load parameters
        self.camera_frame = self.get_parameter("base_frame").value
        self.control_rate = self.get_parameter("control_rate").value
        self.timeout_no_detection = self.get_parameter("timeout_no_detection").value
        self.pan_joint = self.get_parameter("pan_joint").value
        self.tilt_joint = self.get_parameter("tilt_joint").value

        # QoS Profiles
        qos_sensor = QoSPresetProfiles.SENSOR_DATA.value
        qos_default = QoSPresetProfiles.SYSTEM_DEFAULT.value

        # Publishers
        self.goal_pub = self.create_lifecycle_publisher(
            PoseStamped, self.get_parameter("head_goal_topic").value, qos_default
        )
        self.target_sub = self.create_subscription(
            String, self.get_parameter("target_topic").value, self.target_callback, 10
        )

        # Subscribers
        self.camera_info_sub = self.create_subscription(
            CameraInfo, self.get_parameter("camera_info_topic").value, self.camera_info_callback, qos_sensor
        )
        self.face_sub = self.create_subscription(
            FaceRecognitionArray, self.get_parameter("face_topic").value, self.face_callback, qos_sensor
        )
        self.joint_sub = self.create_subscription(
            JointState, "/wxxms/joint_states", self.joint_states_callback, 10
        )
        self.target_sub = self.create_subscription(
            String, self.get_parameter("target_topic").value, self.target_callback, 10
        )

        # Control Loop Timer
        timer_period = 1.0 / self.control_rate
        self.control_timer = self.create_timer(timer_period, self.control_loop)

        self.get_logger().info("Node CONFIGURED. Publishers and subscribers are ready.")
        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> Face Tracker ACTIVATED <<<")
        self.is_tracking_active = True
        self._reset_tracking_state()
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> Face Tracker DEACTIVATED <<<")
        self.is_tracking_active = False
        return super().on_deactivate(state)
        
    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.destroy_timer(self.control_timer)
        self.destroy_subscription(self.camera_info_sub)
        self.destroy_subscription(self.face_sub)
        self.destroy_subscription(self.joint_sub)
        self.destroy_subscription(self.target_sub)
        return TransitionCallbackReturn.SUCCESS

    # --- Helper Methods ---

    def _reset_tracking_state(self):
        """Clears smoothing history and resets PIDs to prevent sudden jumps."""
        self.smoothed_pixel_x = None
        self.smoothed_pixel_y = None
        current_time = self.get_clock().now().nanoseconds / 1e9
        self.last_detection_time = current_time
        self.last_control_time = current_time

    # --- Callbacks ---

    def target_callback(self, msg: String):
        """Receives the ID of the person the robot should track."""
        self.target_id = msg.data
        self.get_logger().info(f"New tracking target set: ID {self.target_id}")
        self._reset_tracking_state()

    def joint_states_callback(self, msg: JointState):
        """Updates the current mechanical position of the head."""
        if not self.is_tracking_active:
            return
            
        try:
            idx_pan = msg.name.index(self.pan_joint)
            idx_tilt = msg.name.index(self.tilt_joint)
            self.current_pan = msg.position[idx_pan]
            self.current_tilt = msg.position[idx_tilt]
        except ValueError:
            # Expected joints not found in this specific message
            pass

    def camera_info_callback(self, msg: CameraInfo):
        """Extracts camera intrinsic parameters (Pinhole model)."""
        if not self.camera_info_ready:
            self.fx, self.fy = msg.k[0], msg.k[4]
            self.cx, self.cy = msg.k[2], msg.k[5]
            self.camera_info_ready = True

    def face_callback(self, msg: FaceRecognitionArray):
        """Processes face bounding boxes and applies EMA smoothing."""
        if not self.is_tracking_active or not self.camera_info_ready or not msg.recognitions:
            return

        target_detection = None

        # 1. Find the face that matches our target_id
        if self.target_id:
            for recog, det in zip(msg.recognitions, msg.detections):
                if recog.classified_id == self.target_id:
                    target_detection = det
                    break
        
        # 2. Fallback: track the largest face if no target is specified or target is lost
        if not target_detection:
            target_detection = max(msg.detections, key=lambda d: d.width * d.height)

        # Calculate center of the bounding box (offsetting Y slightly upwards for eye-level tracking)
        raw_x = target_detection.corner.x + (target_detection.width / 2.0)
        raw_y = target_detection.corner.y + (target_detection.height * 0.15)

        # Apply Exponential Moving Average (EMA) for basic noise reduction
        alpha = self.get_parameter("ema_alpha").value
        
        if self.smoothed_pixel_x is None:
            self.smoothed_pixel_x = raw_x
            self.smoothed_pixel_y = raw_y
        else:
            self.smoothed_pixel_x = alpha * raw_x + (1 - alpha) * self.smoothed_pixel_x
            self.smoothed_pixel_y = alpha * raw_y + (1 - alpha) * self.smoothed_pixel_y
        
        self.last_detection_time = self.get_clock().now().nanoseconds / 1e9
        self.new_detection_ready = True

    # --- Main Control Loop ---

    def control_loop(self):
        """Calculates direct geometric angles to command the head in position mode."""
        if not self.is_tracking_active or not self.camera_info_ready or self.smoothed_pixel_x is None:
            self.last_control_time = self.get_clock().now().nanoseconds / 1e9
            return

        # Ensure we only calculate on fresh detections to prevent double-ticking
        if not self.new_detection_ready:
            return
        self.new_detection_ready = False

        now = self.get_clock().now().nanoseconds / 1e9
        time_since_last_detection = now - self.last_detection_time

        if time_since_last_detection > self.timeout_no_detection:
            self._reset_tracking_state()
            return

        # 1. Calculate Pixel Error
        err_x_pixel = self.smoothed_pixel_x - self.cx
        err_y_pixel = self.smoothed_pixel_y - self.cy

        # Vision Deadzone (Ignore micro-movements)
        if abs(err_x_pixel) < 40: err_x_pixel = 0.0
        if abs(err_y_pixel) < 30: err_y_pixel = 0.0

        # 2. Geometric Angle Calculation (Exact angle to target)
        err_pan_angle = -math.atan2(err_x_pixel, self.fx)
        err_tilt_angle = math.atan2(err_y_pixel, self.fy)

        # 3. Apply Proportional Gain (Acts as a smoothing interpolator, not a true PID P-term)
        # A value of 1.0 means "snap instantly to the target". 
        # A value of 0.2 means "move 20% of the way to the target this frame".
        p_pan = self.get_parameter("p_gain_pan").value
        p_tilt = self.get_parameter("p_gain_tilt").value
        
        delta_pan = err_pan_angle * p_pan
        delta_tilt = err_tilt_angle * p_tilt

        # 4. Hardware Deadzone (CRITICAL FOR POSITION MODE)
        # If the requested movement is less than ~0.5 degrees (0.008 rad), DO NOT send a command.
        # This gives the Dynamixel servos time to rest and stops micro-stuttering.
        if abs(delta_pan) < 0.008 and abs(delta_tilt) < 0.008:
            return

        # 5. Calculate Absolute Joint Commands
        target_pan = self.current_pan + delta_pan
        target_tilt = self.current_tilt + delta_tilt

        # 6. Publish PoseStamped goal
        msg = PoseStamped()
        msg.header = Header(stamp=self.get_clock().now().to_msg(), frame_id=self.camera_frame)
        
        # Orientation: Roll=0, Pitch=Tilt, Yaw=Pan
        q = tf_transformations.quaternion_from_euler(0.0, target_tilt, target_pan)
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.goal_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = FaceTrackerLifecycle()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()