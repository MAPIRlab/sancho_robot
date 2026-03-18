#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class JointStateMerger(Node):
    """
    A ROS2 Node that merges joint state messages from two different topics.

    This node subscribes to two JointState topics ('/wxxms/joint_states' and '/joint_states_urdf'),
    merges their data, and publishes the combined joint states to '/joint_states_merged'.
    When merging, it preserves joint names and their respective position, velocity, and effort values.
    If the same joint appears in both messages, it prioritizes non-zero position values.

    Subscriptions:
        - /wxxms/joint_states (sensor_msgs/JointState): First source of joint states
        - /joint_states_urdf (sensor_msgs/JointState): Second source of joint states

    Publications:
        - /joint_states_merged (sensor_msgs/JointState): Combined joint states from both sources

    Parameters:
        None

    Note:
        The node publishes merged joint states at 50 Hz regardless of input message rates.
    """
    def __init__(self):
        super().__init__("joint_state_merger")
        self.joints_1 = JointState()
        self.joints_2 = JointState()

        self.pub = self.create_publisher(JointState, "/joint_states_merged", 10)
        self.sub1 = self.create_subscription(
            JointState, "/wxxms/joint_states", self.cb1, 10
        )
        self.sub2 = self.create_subscription(
            JointState, "/joint_states_urdf", self.cb2, 10
        )

        self.timer = self.create_timer(0.02, self.publish_merged)  # 50 Hz

    def cb1(self, msg):
        self.joints_1 = msg

    def cb2(self, msg):
        self.joints_2 = msg

    def publish_merged(self):
        merged = JointState()
        merged.header.stamp = self.get_clock().now().to_msg()

        joint_map = {}

        def add_to_map(source):
            for i, name in enumerate(source.name):
                pos = source.position[i] if i < len(source.position) else 0.0
                vel = source.velocity[i] if i < len(source.velocity) else 0.0
                eff = source.effort[i] if i < len(source.effort) else 0.0

                if name not in joint_map:
                    joint_map[name] = (pos, vel, eff)
                else:
                    old_pos, old_vel, old_eff = joint_map[name]
                    # Prefer new if old position is 0.0 and new is not
                    if old_pos == 0.0 and pos != 0.0:
                        joint_map[name] = (pos, vel, eff)

        add_to_map(self.joints_1)
        add_to_map(self.joints_2)

        for name, (pos, vel, eff) in joint_map.items():
            merged.name.append(name)
            merged.position.append(pos)
            merged.velocity.append(vel)
            merged.effort.append(eff)

        self.pub.publish(merged)


def main(args=None):
    rclpy.init(args=args)
    node = JointStateMerger()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
