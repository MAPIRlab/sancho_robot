import math
import numpy as np
import cv2

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile

from std_msgs.msg import Float32
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class DOAOverlayNode(Node):
    def __init__(self):
        super().__init__("doa_overlay")

        # IMPORTANTE: si cambia la cámara hay que ajustar estos intrínsecos (K) y resolución (W,H)
        self.W = 1920
        self.H = 1080
        self.fx = 1071.31955
        self.fy = 1075.42921
        self.cx = 939.37064
        self.cy = 484.21201

        self.declare_parameters(namespace='', parameters=[
            ("camera_image_topic", "/sancho_camera/image_raw"),
            ("doa_topic", "/sancho_audio/doa"),
            ("doa_overlay_topic", "/sancho_camera/image_audio_doa"),
            ("mic_to_cam_yaw_deg", 0.0),
            ("max_doa_age_ms", 250.0)
        ])

        img_topic = self.get_parameter("camera_image_topic").get_parameter_value().string_value
        doa_topic = self.get_parameter("doa_topic").get_parameter_value().string_value
        doa_overlay_topic = self.get_parameter("doa_overlay_topic").get_parameter_value().string_value

        self.bridge = CvBridge()
        self.last_doa = None

        qos_cam = QoSProfile(depth=5)
        qos_doa = QoSProfile(depth=10)

        self.sub_img = self.create_subscription(Image, img_topic, self.on_image, qos_cam)
        self.sub_doa = self.create_subscription(Float32, doa_topic, self.on_doa, qos_doa)
        self.pub = self.create_publisher(Image, doa_overlay_topic, qos_cam)

        self.get_logger().info("Audio DOA Overlay Node initializated succesfully")

    def on_doa(self, msg: Float32):
        self.last_doa = float(msg.data)

    def on_image(self, msg: Image):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        doa = None if (self.last_doa is None or math.isnan(self.last_doa)) else self.last_doa
        out = self.draw_overlay(frame, doa)
        self.pub.publish(self.bridge.cv2_to_imgmsg(out, encoding="bgr8"))

    def draw_overlay(self, frame, doa_deg):
        h, w = frame.shape[:2]
        cx, fx = self.cx, self.fx

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

        if doa_deg is not None:
            yaw_off = float(self.get_parameter("mic_to_cam_yaw_deg").get_parameter_value().double_value)
            theta = max(-89.9, min(89.9, float(doa_deg) + yaw_off))
            x_col = int(round(cx + fx * math.tan(math.radians(theta))))
            x_col = max(0, min(w - 1, x_col))

            cv2.line(frame, (x_col, 0), (x_col, h), (255, 0, 0), 4, cv2.LINE_AA)
            put_label(frame, f"{theta:+.1f} deg", x_col + 10, mid_y)
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
