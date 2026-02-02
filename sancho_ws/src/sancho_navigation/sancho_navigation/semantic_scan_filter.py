#!/usr/bin/env python3

import math
import copy
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.time import Time

from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import tf_transformations


class SemanticScanFilter(Node):

    def __init__(self):
        super().__init__('semantic_scan_filter')

        # -------- Parameters --------
        self.declare_parameter('persistent_fov_deg', 120.0)
        self.declare_parameter('max_angular_velocity', 0.4)
        self.declare_parameter('max_yaw_covariance', 0.08)
        self.declare_parameter('passthrough_if_unhealthy', True)
        self.declare_parameter('base_frame', 'base_link')

        self.persistent_fov = math.radians(
            self.get_parameter('persistent_fov_deg').value
        )
        self.max_omega = self.get_parameter('max_angular_velocity').value
        self.max_yaw_cov = self.get_parameter('max_yaw_covariance').value
        self.passthrough = self.get_parameter(
            'passthrough_if_unhealthy').value
        self.base_frame = self.get_parameter('base_frame').value

        # -------- State --------
        self.current_omega = 0.0
        self.current_yaw_cov = float('inf')

        # -------- TF --------
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # -------- Publishers --------
        self.pub_persistent = self.create_publisher(
            LaserScan, '/scan_persistent', 10)
        self.pub_non_persistent = self.create_publisher(
            LaserScan, '/scan_non_persistent', 10)

        # -------- Subscribers --------
        self.create_subscription(
            LaserScan, '/scan_1st', self.scan_cb, 10)
        self.create_subscription(
            LaserScan, '/scan_2nd', self.scan_cb, 10)
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

    def scan_cb(self, scan: LaserScan):
        """Generic callback for any laser scan"""
        self.process_scan(scan)

    def process_scan(self, scan: LaserScan):
        # Verificación rápida de salud
        if (abs(self.current_omega) >= self.max_omega or 
            self.current_yaw_cov >= self.max_yaw_cov) and self.passthrough:
            self.pub_non_persistent.publish(scan)
            return

        try:
            # Look up transform from base_link to laser frame
            # We use the latest available transform
            trans = self.tf_buffer.lookup_transform(
                self.base_frame,
                scan.header.frame_id,
                rclpy.time.Time())
        except TransformException as ex:
            # Only log periodically to avoid spamming if TF is missing initially
            # self.get_logger().debug(f'Could not transform {scan.header.frame_id}: {ex}')
            return

        # Extract yaw from quaternion
        q = trans.transform.rotation
        _, _, yaw_offset = tf_transformations.euler_from_quaternion(
            [q.x, q.y, q.z, q.w])
        
        tx = trans.transform.translation.x
        ty = trans.transform.translation.y

        ranges = np.array(scan.ranges)
        
        # Calculate local angles of the scan points
        local_angles = np.linspace(scan.angle_min, scan.angle_max, len(ranges))
        
        # --- Transform to Base Frame ---
        # 1. Convert to Cartesian in Laser Frame
        # Note: We must handle 'inf' carefully. 
        # For projection purposes, we treat Infs as effectively very far away along their ray.
        # But mathematically x/y will be inf.
        
        # Avoid warnings with infs
        valid_mask = np.isfinite(ranges)
        
        # We need an array for angles_base. Initialize with something.
        angles_base = np.zeros_like(ranges)
        
        # --- Valid Points ---
        if np.any(valid_mask):
            r_valid = ranges[valid_mask]
            a_valid = local_angles[valid_mask]
            
            x_local = r_valid * np.cos(a_valid)
            y_local = r_valid * np.sin(a_valid)
            
            c, s = np.cos(yaw_offset), np.sin(yaw_offset)
            x_base = x_local * c - y_local * s + tx
            y_base = x_local * s + y_local * c + ty
            
            angles_base[valid_mask] = np.arctan2(y_base, x_base)
            
        # --- Infinite Points ---
        # For points at infinity, the translation (tx, ty) is negligible.
        # The angle is simply local_angle + yaw_offset.
        inf_mask = ~valid_mask
        if np.any(inf_mask):
             inf_angles = (local_angles[inf_mask] + yaw_offset + np.pi) % (2 * np.pi) - np.pi
             angles_base[inf_mask] = inf_angles

        # --- Filtering ---
        # Persistent: Rear of robot.
        # Rear is defined as angle > (pi - fov/2) OR angle < -(pi - fov/2)
        # effectively abs(angle) > (pi - fov/2)
        
        mask_persistent = np.abs(angles_base) > (np.pi - self.persistent_fov / 2)
        
        scan_p = self.empty_clone(scan)
        scan_np = self.empty_clone(scan)

        p_ranges = np.full_like(ranges, np.inf)
        np_ranges = np.full_like(ranges, np.inf)

        # Points in the "Rear" (Persistent) region go to scan_p
        p_ranges[mask_persistent] = ranges[mask_persistent]
        
        # Points in the "Front" (Non-Persistent) region go to scan_np
        np_ranges[~mask_persistent] = ranges[~mask_persistent]

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
