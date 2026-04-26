#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
import json

# Action Types
from nav2_msgs.action import NavigateToPose
from sancho_interfaces.action import PlayTTS, RotateHead, TurnToAngle, ListenVoice

# Service Types
from sancho_interfaces.srv import GetCentralFaceCluster, SanchoPrompt, GreetPeople, SocialState

# Topic Types
from sensor_msgs.msg import BatteryState
from nav_msgs.msg import Odometry
from std_msgs.msg import String

class SanchoMockEnvironment(Node):
    def __init__(self):
        super().__init__('sancho_mock_env')
        self.get_logger().info('Initializing Sancho Mock Environment...')

        # --- PARAMETERS ---
        self.declare_parameter('sim_battery_percentage', 80.0)
        self.declare_parameter('sim_battery_current', -0.5)
        self.declare_parameter('sim_odom_x', 0.0)
        self.declare_parameter('sim_odom_y', 0.0)

        # --- ACTIONS ---
        self._as_nav = ActionServer(self, NavigateToPose, '/navigate_to_pose', self.execute_nav)
        self._as_rotate = ActionServer(self, RotateHead, '/head_controller/rotate', self.execute_rotate)
        self._as_turn = ActionServer(self, TurnToAngle, '/attention_controller/turn_to_angle', self.execute_turn)
        self._as_turn_head = ActionServer(self, TurnToAngle, '/head_controller/turn_to_angle', self.execute_turn)

        # --- SERVICES ---
        self._srv_cluster = self.create_service(GetCentralFaceCluster, '/central_faces_cluster_node/get_central_cluster', self.srv_cluster_cb)
        self._srv_greet = self.create_service(GreetPeople, 'assistant/greet_people', self.srv_greet_cb)
        self._srv_social = self.create_service(SocialState, '/social_state', self.srv_social_cb)

        # --- TOPIC PUBLISHERS ---
        self._pub_battery = self.create_publisher(BatteryState, '/battery_state', 10)
        self._pub_odom = self.create_publisher(Odometry, '/odom', 10)
        self._pub_speaker = self.create_publisher(String, '/active_speaker_info', 10)
        self._pub_mock_speech = self.create_publisher(String, '/sancho/mock_speech', 10)

        # Timer to publish sensor data at 5Hz
        self.create_timer(0.2, self.timer_cb)

        self.conv_turns = 0
        self.get_logger().info('Mock Environment Ready. Waiting for goals/requests...')

    def timer_cb(self):
        # Read current parameter values
        perc = self.get_parameter('sim_battery_percentage').value
        curr = self.get_parameter('sim_battery_current').value
        x = self.get_parameter('sim_odom_x').value
        y = self.get_parameter('sim_odom_y').value

        # Publish Battery
        batt = BatteryState()
        batt.percentage = float(perc)
        batt.current = float(curr)
        self._pub_battery.publish(batt)

        # Publish Odom
        odom = Odometry()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose.position.x = float(x)
        odom.pose.pose.position.y = float(y)
        self._pub_odom.publish(odom)

        # Publish Default Speaker
        speaker = String()
        speaker.data = '{"id": "0", "name": "amigo"}'
        self._pub_speaker.publish(speaker)

    # --- Action Callbacks ---
    def execute_nav(self, goal_handle):
        self.get_logger().info(f'Navigating to: {goal_handle.request.pose.pose.position}')
        goal_handle.succeed()
        return NavigateToPose.Result()

    def execute_rotate(self, goal_handle):
        self.get_logger().info(f'Rotating head: {goal_handle.request.target_angle_deg} degrees')
        goal_handle.succeed()
        return RotateHead.Result()

    def execute_turn(self, goal_handle):
        self.get_logger().info(f'Turning to angle...')
        goal_handle.succeed()
        return TurnToAngle.Result()

    # --- Service Callbacks ---
    def srv_cluster_cb(self, request, response):
        self.get_logger().info('Cluster request received')
        response.ids = ["1"]
        response.names = ["Amigo"]
        return response

    def srv_greet_cb(self, request, response):
        self.get_logger().info('Greet people request received')
        return response

    def srv_social_cb(self, request, response):
        self.get_logger().info(f'Social state update: {request.state}')
        return response

def main(args=None):
    rclpy.init(args=args)
    node = SanchoMockEnvironment()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
