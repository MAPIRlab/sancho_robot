import time
import math
import threading

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
from tf_transformations import quaternion_from_euler

from sancho_interfaces.action import RotateHead


class HeadActionServer(Node):
    def __init__(self):
        super().__init__('head_action_server')

        # Parameters
        self.declare_parameter('joint_name', 'pan')
        self.declare_parameter('tolerance_deg', 5.0)
        self.declare_parameter('min_angle_deg', -90.0)
        self.declare_parameter('max_angle_deg', 90.0)
        
        self.joint_name = self.get_parameter('joint_name').value
        self.tolerance_rad = math.radians(self.get_parameter('tolerance_deg').get_parameter_value().double_value)
        self.min_angle_deg = self.get_parameter('min_angle_deg').get_parameter_value().double_value
        self.max_angle_deg = self.get_parameter('max_angle_deg').get_parameter_value().double_value

        # State variables
        self._current_angle_rad = 0.0
        self._state_lock = threading.Lock() # Thread safety

        # Allow multiple threads on callback group
        self.cb_group = ReentrantCallbackGroup()

        # Publisher
        self.goal_pub = self.create_publisher(
            PoseStamped, 
            '/head_goal', 
            10
        )

        # Subscriber
        self.joint_sub = self.create_subscription(
            JointState, 
            '/wxxms/joint_states', 
            self._joint_states_callback, 
            10,
            callback_group=self.cb_group
        )

        # Action server
        self._action_server = ActionServer(
            self,
            RotateHead,
            '/head_controller/rotate',
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )
        
        self.get_logger().info("Head Action Server initialized and ready to receive goals")

    def _joint_states_callback(self, msg: JointState):
        """Updates head state in real time"""
        try:
            # Try exact match or suffix match (e.g. 'pan' or 'wxxms/pan')
            index = -1
            for i, name in enumerate(msg.name):
                if name == self.joint_name or name.endswith('/' + self.joint_name):
                    index = i
                    break
            
            if index != -1:
                with self._state_lock:
                    self._current_angle_rad = msg.position[index]
            else:
                # Log once every 100 messages if joint not found to avoid spamming
                if not hasattr(self, '_log_counter'): self._log_counter = 0
                self._log_counter += 1
                if self._log_counter % 100 == 0:
                    self.get_logger().warn(f"Joint '{self.joint_name}' not found in current JointState. Available: {msg.name}")
        except Exception as e:
            self.get_logger().error(f"Error in joint_states callback: {e}")

    # --- Action callbacks ---
    def goal_callback(self, goal_request):
        """Accepts or rejects goal request"""
        self.get_logger().info(f"Goal received: Rotate to {goal_request.target_angle_deg}º")
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        """Manages what happens when rotation is cancelled"""
        self.get_logger().warn("¡Rotation cancelled by client!")
        
        with self._state_lock:
            stop_angle = self._current_angle_rad
        self._publish_head_pose(math.degrees(stop_angle))
        
        return CancelResponse.ACCEPT

    # --- Execution loop ---
    def execute_callback(self, goal_handle):
        """Executes head rotation"""
        target_deg = goal_handle.request.target_angle_deg
        timeout_sec = goal_handle.request.timeout_sec

        clamped_deg = max(min(target_deg, self.max_angle_deg), self.min_angle_deg)
        
        if clamped_deg != target_deg:
            self.get_logger().info(f"Angle {target_deg}º out of bounds. Rotating to {clamped_deg}º instead")
            
        target_rad = math.radians(clamped_deg)
        
        # Send head command
        self._publish_head_pose(clamped_deg)

        start_time = time.time()
        feedback_msg = RotateHead.Feedback()
        result_msg = RotateHead.Result()
        
        while rclpy.ok():
            # Check cancelation
            if goal_handle.is_cancel_requested:
                result_msg.success = False
                result_msg.message = "Cancelado"
                with self._state_lock:
                    result_msg.final_angle_deg = math.degrees(self._current_angle_rad)
                
                goal_handle.canceled()
                return result_msg

            # Read head current state
            with self._state_lock:
                current_rad = self._current_angle_rad

            error_rad = abs(target_rad - current_rad)

            # Check if we are done
            if error_rad <= self.tolerance_rad:
                self.get_logger().info("Goal reached")
                result_msg.success = True
                result_msg.message = "Success"
                result_msg.final_angle_deg = math.degrees(current_rad)
                goal_handle.succeed()
                return result_msg

            # Check timeout
            if (time.time() - start_time) > timeout_sec:
                self.get_logger().warn("Timeout reached. Aborting rotation.")
                result_msg.success = False
                result_msg.message = "Timeout"
                result_msg.final_angle_deg = math.degrees(current_rad)
                goal_handle.abort()
                return result_msg

            # Publish feedback
            feedback_msg.current_angle_deg = math.degrees(current_rad)
            feedback_msg.distance_remaining = math.degrees(error_rad)
            goal_handle.publish_feedback(feedback_msg)
            
            time.sleep(0.1) 

    def _publish_head_pose(self, angle_deg: float):
        angle_rad = max(min(math.radians(angle_deg), math.radians(100.0)), math.radians(-100.0))
        q = quaternion_from_euler(0.0, math.radians(-30.0), angle_rad)

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.get_logger().info(f"Publishing to /head_goal: pan={angle_deg:.2f}º")
        self.goal_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = HeadActionServer()
    
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("Head Action Server stopped")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()