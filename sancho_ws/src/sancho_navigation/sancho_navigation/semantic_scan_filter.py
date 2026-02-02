#!/usr/bin/env python3

import math
import copy
import numpy as np

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped


class SemanticScanFilter(Node):

    def __init__(self):
        super().__init__('semantic_scan_filter')

        # -------- Parameters --------
        self.declare_parameter('persistent_fov_deg', 120.0)
        self.declare_parameter('max_angular_velocity', 0.4)
        self.declare_parameter('max_yaw_covariance', 0.08)
        self.declare_parameter('passthrough_if_unhealthy', True)

        self.persistent_fov = math.radians(
            self.get_parameter('persistent_fov_deg').value
        )
        self.max_omega = self.get_parameter('max_angular_velocity').value
        self.max_yaw_cov = self.get_parameter('max_yaw_covariance').value
        self.passthrough = self.get_parameter(
            'passthrough_if_unhealthy').value

        # -------- State --------
        self.current_omega = 0.0
        self.current_yaw_cov = float('inf')

        # -------- Publishers --------
        self.pub_persistent = self.create_publisher(
            LaserScan, '/scan_persistent', 10)
        self.pub_non_persistent = self.create_publisher(
            LaserScan, '/scan_non_persistent', 10)

        # -------- Subscribers --------
        self.create_subscription(
            LaserScan, '/scan_1st', self.scan_front_cb, 10)
        self.create_subscription(
            LaserScan, '/scan_2nd', self.scan_back_cb, 10)
        self.create_subscription(
            Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.amcl_cb,
            10
        )

        self.get_logger().info('SemanticScanFilter started')

    # ---------------- Callbacks ----------------

    def odom_cb(self, msg: Odometry):
        self.current_omega = msg.twist.twist.angular.z

    def amcl_cb(self, msg: PoseWithCovarianceStamped):
        # yaw covariance = index 35
        self.current_yaw_cov = msg.pose.covariance[35]

    def scan_front_cb(self, scan: LaserScan):
        """Láser frontal: normalmente non-persistent"""
        self.process_scan(scan, persistent=False)

    def scan_back_cb(self, scan: LaserScan):
        """Láser trasero: normalmente persistent"""
        self.process_scan(scan, persistent=True)

    def process_scan(self, scan: LaserScan, persistent: bool):
        # Verificación rápida de salud
        if (abs(self.current_omega) >= self.max_omega or 
            self.current_yaw_cov >= self.max_yaw_cov) and self.passthrough:
            self.pub_non_persistent.publish(scan)
            return

        ranges = np.array(scan.ranges)
        angles = np.linspace(scan.angle_min, scan.angle_max, len(ranges))
        wrapped_angles = (angles + np.pi) % (2 * np.pi) - np.pi

        # Definir máscara según persistent o non-persistent
        if persistent:
            mask = np.abs(wrapped_angles) > (np.pi - self.persistent_fov / 2)
        else:
            mask = np.abs(wrapped_angles) <= (np.pi - self.persistent_fov / 2)

        scan_p = self.empty_clone(scan)
        scan_np = self.empty_clone(scan)

        p_ranges = np.full_like(ranges, np.inf)
        np_ranges = np.full_like(ranges, np.inf)

        p_ranges[mask] = ranges[mask]
        np_ranges[~mask] = ranges[~mask]

        scan_p.ranges = p_ranges.tolist()
        scan_np.ranges = np_ranges.tolist()

        self.pub_persistent.publish(scan_p)
        self.pub_non_persistent.publish(scan_np)

    # ---------------- Utilities ----------------

    def empty_clone(self, scan: LaserScan) -> LaserScan:
        new_scan = copy.deepcopy(scan)
        new_scan.ranges = [float('inf')] * len(scan.ranges)
        return new_scan


def main():
    rclpy.init()
    node = SemanticScanFilter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
