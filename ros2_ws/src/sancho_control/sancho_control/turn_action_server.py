import time
import math
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from nav2_msgs.action import Spin
from tf_transformations import quaternion_from_euler, euler_from_quaternion

from sancho_interfaces.action import TurnToAngle 

class TurnActionServer(Node):
    def __init__(self):
        super().__init__('turn_action_server')

        self.current_yaw_deg = 0.0
        
        # Callback Group
        self.cb_group = ReentrantCallbackGroup()

        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10,
            callback_group=self.cb_group
        )

        self.head_goal_pub = self.create_publisher(
            PoseStamped, 
            '/head_goal', 
            10
        )

        self.spin_client = ActionClient(
            self, 
            Spin, 
            '/spin', 
            callback_group=self.cb_group
        )

        self._action_server = ActionServer(
            self,
            TurnToAngle,
            '/attention_controller/turn_to_angle',
            execute_callback=self.execute_callback,
            callback_group=self.cb_group
        )
        
        self.get_logger().info("Turn Action Server initialized.")

    def odom_callback(self, msg: Odometry):
        q = msg.pose.pose.orientation
        _, _, yaw_rad = euler_from_quaternion([q.x, q.y, q.z, q.w])
        self.current_yaw_deg = math.degrees(yaw_rad)

    def normalize_angle(self, angle):
        angle_rad = math.radians(angle)
        angle_rad_norm = math.atan2(math.sin(angle_rad), math.cos(angle_rad))
        return math.degrees(angle_rad_norm)

    def publish_head_pose(self, angle_deg: float):
        angle_rad = math.radians(angle_deg)
        q = quaternion_from_euler(0.0, math.radians(-30.0), angle_rad)

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.head_goal_pub.publish(msg)

    def execute_callback(self, goal_handle):
        target_abs_deg = goal_handle.request.absolute_target_angle_deg
        relative_spin_deg = self.normalize_angle(target_abs_deg - self.current_yaw_deg)

        # --- STEP 1: Quick look ---
        clamped_initial_head = max(min(relative_spin_deg, 90.0), -90.0)
        self.get_logger().info(f"Rotating head to {clamped_initial_head}º")
        self.publish_head_pose(clamped_initial_head)
        
        # Small pause so that head reacts before base
        time.sleep(np.random.uniform(0.3, 1.0)) 

        # --- STEP 2: Start base spin ---
        if not self.spin_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error("Spin action server not available")
            goal_handle.abort()
            return TurnToAngle.Result(success=False)

        spin_goal = Spin.Goal()
        spin_goal.target_yaw = math.radians(relative_spin_deg)
        
        # Send spinning goal
        self.get_logger().info(f"Sending spinning goal: {relative_spin_deg}º (target is {target_abs_deg}º abs).")
        self.is_spinning = True
        
        # Wait for goal to be accepted
        future = self.spin_client.send_goal_async(spin_goal)
        while not future.done():
            time.sleep(0.1)
            
        spin_goal_handle = future.result()
        if not spin_goal_handle.accepted:
            self.get_logger().error("Spin goal rejected")
            self.is_spinning = False
            goal_handle.abort()
            return TurnToAngle.Result(success=False)

        self.get_logger().info(f"Spin goal accepted")

        # --- STEP 3: Compensate head rotation ---
        last_head_angle = None

        # While base is moving, adjust properly head rotation
        result_future = spin_goal_handle.get_result_async()
        while not result_future.done():
            # Check if goal is cancelled
            if goal_handle.is_cancel_requested:
                self.get_logger().warn('Cancelling turning action...')
                spin_goal_handle.cancel_goal_async()
                goal_handle.canceled()
                return TurnToAngle.Result(success=False)
            
            # Compensate head rotation
            diff = self.normalize_angle(target_abs_deg - self.current_yaw_deg)
            
            if last_head_angle is None or abs(diff - last_head_angle) >= 1.5:
                self.publish_head_pose(diff)
                last_head_angle = diff

            time.sleep(0.05) # 20 Hz


        # --- ACTION IS DONE ---
        result = result_future.result()
        
        if result.status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('Turning action completed successfully by Nav2')
            goal_handle.succeed()
            return TurnToAngle.Result(success=True)
            
        elif result.status == GoalStatus.STATUS_ABORTED:
            self.get_logger().error('Nav2 ABORTED the spin! (Check the costmap, obstacle detected)')
            goal_handle.abort()
            return TurnToAngle.Result(success=False)
            
        else:
            self.get_logger().warn(f'Spin finished with abnormal status code: {result.status}')
            goal_handle.abort()
            return TurnToAngle.Result(success=False)

def main(args=None):
    rclpy.init(args=args)
    node = TurnActionServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("Stopping Turn Action Server...")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()