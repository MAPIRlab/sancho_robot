import numpy as np
from scipy.spatial.transform import Rotation as R_scipy
import rclpy
from tf2_ros import Buffer, TransformListener
from tf2_ros import LookupException, ConnectivityException, ExtrapolationException
from sensor_msgs.msg import CameraInfo # Added import

class RotationalEgoMotion:
    def __init__(self, node, camera_info_topic='/sancho_camera/camera_info', camera_frame="nose_camera_link", base_frame="odom"):
        self.node = node
        self.camera_frame = camera_frame
        self.base_frame = base_frame
        
        # TF Setup
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self.node)
        self.prev_time = None
        
        # Intrinsics will be populated dynamically
        self.k = None
        self.k_inv = None
        
        # Subscribe to CameraInfo
        self.node.get_logger().info(f"Waiting for camera intrinsics on {camera_info_topic}...")
        self.camera_info_sub = self.node.create_subscription(
            CameraInfo,
            camera_info_topic,
            self._camera_info_callback,
            10
        )

    def _camera_info_callback(self, msg):
        """Extracts the k matrix once and destroys the subscriber."""
        # msg.k is a flat tuple of 9 elements: (fx, 0, cx, 0, fy, cy, 0, 0, 1)
        self.k = np.array(msg.k).reshape((3, 3))
        self.k_inv = np.linalg.inv(self.k)
        
        self.node.get_logger().info("Camera intrinsics successfully loaded from /camera_info.")
        
        # We only need this once. Destroying the subscriber saves resources.
        self.node.destroy_subscription(self.camera_info_sub)
        self.camera_info_sub = None

    def compensate(self, tracks, current_time):
        if not tracks or self.k is None:
            self.prev_time = current_time
            return

        try:
            # 1. Lower the timeout to 2ms (0.002)
            # 2. Use a 'time_tolerance' or lookup the latest transform if exact fails
            t = self.tf_buffer.lookup_transform_full(
                target_frame=self.camera_frame,
                target_time=current_time,
                source_frame=self.camera_frame,
                source_time=self.prev_time,
                fixed_frame=self.base_frame, 
                timeout=rclpy.duration.Duration(seconds=0.002) # REDUCED TIMEOUT
            )
            
            q = t.transform.rotation
            R = R_scipy.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
            H = self.k @ R @ self.k_inv
            
            for track in tracks:
                center = np.array([track.mean[0], track.mean[1], 1.0])
                warped_center = H @ center
                if warped_center[2] != 0:
                    warped_center /= warped_center[2]
                    track.mean[0] = warped_center[0]
                    track.mean[1] = warped_center[1]

        except (LookupException, ConnectivityException, ExtrapolationException):
            # If we hit the 2ms timeout, we skip compensation for this frame 
            # to keep the CPU free for YOLOX.
            pass

        self.prev_time = current_time