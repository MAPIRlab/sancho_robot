import math
import cv2

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32
from sensor_msgs.msg import Image, JointState, CameraInfo
from cv_bridge import CvBridge


class DOAOverlayNode(Node):
    def __init__(self):
        super().__init__("doa_overlay")

        self.last_doa = None

        # Head yaw (deg) read from joint_states (pan joint). Used as mic->cam yaw offset
        self.head_yaw_deg = None

        # Camera parameters
        self.fx = None
        self.cx = None

        self.bridge = CvBridge()
        
        self.declare_parameter("camera_image_topic", "/sancho_camera/image_rect")
        self.declare_parameter("camera_info_topic", "/sancho_camera/camera_info")
        self.declare_parameter("doa_topic", "/sancho_audio/doa")
        self.declare_parameter("doa_overlay_topic", "/sancho_camera/image_audio_doa")
        self.declare_parameter("joint_states_topic", "/wxxms/joint_states")
        self.declare_parameter("pan_joint", "pan")
        self.declare_parameter("mic_to_cam_yaw_deg", 0.0)  # fallback if joint_states not available
        self.declare_parameter("max_doa_age_ms", 250.0)

        img_topic = self.get_parameter("camera_image_topic").get_parameter_value().string_value
        info_topic = self.get_parameter("camera_info_topic").get_parameter_value().string_value
        doa_topic = self.get_parameter("doa_topic").get_parameter_value().string_value
        doa_overlay_topic = self.get_parameter("doa_overlay_topic").get_parameter_value().string_value
        joint_states_topic = self.get_parameter("joint_states_topic").get_parameter_value().string_value
        self.pan_joint = self.get_parameter("pan_joint").get_parameter_value().string_value
        self.head_yaw_param = float(self.get_parameter("mic_to_cam_yaw_deg").get_parameter_value().double_value)

        # Subscriptions: rectified image, camera info, DOA and joint_states for head yaw
        self.sub_img = self.create_subscription(Image, img_topic, self.on_image, 5)
        self.sub_info = self.create_subscription(CameraInfo, info_topic, self.on_camera_info, 5)
        self.sub_doa = self.create_subscription(Float32, doa_topic, self.on_doa, 10)
        self.sub_jstates = self.create_subscription(JointState, joint_states_topic, self.on_joint_states, 10)
        
        # Publishers: DOA overlay image
        self.pub = self.create_publisher(Image, doa_overlay_topic, 5)

        self.get_logger().info("Audio DOA Overlay Node initializated succesfully")

    def on_doa(self, msg: Float32):
        self.last_doa = float(msg.data)

    def on_joint_states(self, msg: JointState):
        # Read pan joint position (radians) and convert to degrees
        try:
            idx_pan = msg.name.index(self.pan_joint)
            pan_rad = msg.position[idx_pan]
            self.head_yaw_deg = math.degrees(float(pan_rad))

            self.get_logger().info(f"Head yaw: {self.head_yaw_deg}")
        except ValueError:
            # pan_joint not present in the message
            pass

    def on_camera_info(self, msg: CameraInfo):
        # K = [fx,  0, cx, 
        #       0, fy, cy, 
        #       0,  0,  1]
        
        self.fx = msg.k[0]  # X focal distance
        self.cx = msg.k[2]  # X optic center
        
        self.get_logger().info(f'Camera info: fx={self.fx:.2f}, cx={self.cx:.2f}')
        
        if self.sub_info is not None:
            self.destroy_subscription(self.sub_info)
            self.sub_info = None

    def on_image(self, msg: Image):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        out = self.draw_overlay(frame, self.last_doa)
        self.pub.publish(self.bridge.cv2_to_imgmsg(out, encoding="bgr8"))

    def draw_overlay(self, frame, doa_deg):
        h, w = frame.shape[:2]

        def put_label(img, text, x, y, fs=None):
            font, thk = cv2.FONT_HERSHEY_SIMPLEX, 2
            fs = fs or max(0.8, 0.0012 * max(w, h))
            (tw, th), base = cv2.getTextSize(text, font, fs, thk)
            pad = 6
            x = max(pad, min(w - tw - pad, x))
            y = max(pad + th, min(h - pad, y))
            cv2.rectangle(img, (x - pad, y - th - pad), (x + tw + pad, y + base + pad), (0, 0, 0), -1)
            cv2.putText(img, text, (x, y), font, fs, (0, 0, 0), thk + 2, cv2.LINE_AA)  # contorno
            cv2.putText(img, text, (x, y), font, fs, (0, 255, 0), thk, cv2.LINE_AA)    # texto

        mid_y = int(h * 0.5)

        if doa_deg and self.cx and self.fx:
            # Get image real angle (doa + head yaw)
            yaw_off = self.head_yaw_deg or self.head_yaw_param
            theta = float(doa_deg) + float(yaw_off)
            self.get_logger().info(f"DOA: {doa_deg}\tYaw Offset: {yaw_off}\tTheta: {theta}")
            theta = max(-89.9, min(theta, 89.9))
            
            # Get corresponding image column to draw a line on it
            x_pixel = int(self.cx + self.fx * math.tan(theta)) # pinhole model
            x_pixel = max(0, min(x_pixel, w-1))

            cv2.line(frame, (x_pixel, 0), (x_pixel, h), (255, 0, 0), 4, cv2.LINE_AA)
            put_label(frame, f"{theta:+.1f} deg", x_pixel + 10, mid_y)
        else:
            put_label(frame, "No voice", int(w * 0.05), mid_y)

        return frame


def main(args=None):
    rclpy.init(args=args)
    node = DOAOverlayNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()