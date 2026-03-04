import math
import cv2

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32
from sensor_msgs.msg import Image, JointState, CameraInfo
from sancho_msgs.msg import FaceRecognitionArray, FaceRecognition
from cv_bridge import CvBridge


class DOAActiveSpeakerNode(Node):
    """
    This node uses DoA information to figure out who among all detected persons is the one speaking.

    Parameters:
        camera_image_topic (str): Image topic
        camera_info_topic (str): Topic holding camera information such as focal distance
        joint_states_topic (str): Head joints topic
        pan_joint (str): Name of pan joint
        recognitions_topic (str): Persons recognitions topic
        doa_topic (str): DoA topic
        doa_overlay_topic (str): DoA overlay topic

    Publishers:
        doa_overlay_topic (Image): Publishes camera image with a vertical line representing DoA

    Subscribers:
        camera_image_topic (Image): Subscribes to camera images for processing
        camera_info_topic (CameraInfo): Subscribes to get fx and cx paremeters
        joint_states_topic (JointState): Subscribes to get yaw angle from head joints
        recognitions_topic (FaceRecognitionArray): Subscribes to get persons bounding boxes and identities
        doa_topic (Float32): Subscribes to get DoA
    """
    def __init__(self):
        super().__init__("doa_active_speaker")

        self.last_angle = None
        self.speaker = None

        # Head yaw (deg) read from joint_states (pan joint). Used as mic->cam yaw offset
        self.head_yaw_deg = None

        # Camera parameters
        self.fx = None
        self.cx = None

        self.bridge = CvBridge()
        
        self.declare_parameter("camera_image_topic", "/sancho_camera/image_rect")
        self.declare_parameter("camera_info_topic", "/sancho_camera/camera_info")
        self.declare_parameter("joint_states_topic", "/wxxms/joint_states")
        self.declare_parameter("pan_joint", "pan")
        self.declare_parameter("recognitions_topic", "/face_recognitions")
        self.declare_parameter("doa_topic", "/sancho_audio/doa")
        self.declare_parameter("doa_overlay_topic", "/sancho_camera/image_audio_doa")

        img_topic = self.get_parameter("camera_image_topic").get_parameter_value().string_value
        info_topic = self.get_parameter("camera_info_topic").get_parameter_value().string_value
        joint_states_topic = self.get_parameter("joint_states_topic").get_parameter_value().string_value
        self.pan_joint = self.get_parameter("pan_joint").get_parameter_value().string_value
        recognitions_topic = self.get_parameter("recognitions_topic").get_parameter_value().string_value
        doa_topic = self.get_parameter("doa_topic").get_parameter_value().string_value
        doa_overlay_topic = self.get_parameter("doa_overlay_topic").get_parameter_value().string_value

        # Subscriptions
        self.sub_img = self.create_subscription(Image, img_topic, self.on_image, 5)
        self.sub_info = self.create_subscription(CameraInfo, info_topic, self.on_camera_info, 5)
        self.sub_jstates = self.create_subscription(JointState, joint_states_topic, self.on_joint_states, 10)
        self.sub_recog = self.create_subscription(FaceRecognitionArray, recognitions_topic, self.on_recognitions, 5)
        self.sub_doa = self.create_subscription(Float32, doa_topic, self.on_doa, 10)
        
        # Publishers: DOA overlay image
        self.pub = self.create_publisher(Image, doa_overlay_topic, 5)

        self.get_logger().info("Audio DOA Overlay Node initializated succesfully")

    def on_doa(self, msg: Float32):
        doa_deg = msg.data
        yaw_off = self.head_yaw_deg or 0.0
        angle_deg = float(doa_deg) + float(yaw_off)
        
        self.last_angle = float(angle_deg)
        self.last_audio_time = self.get_clock().now()

    def on_joint_states(self, msg: JointState):
        # Read pan joint position (radians) and convert to degrees
        try:
            idx_pan = msg.name.index(self.pan_joint)
            pan_rad = msg.position[idx_pan]
            self.head_yaw_deg = math.degrees(float(pan_rad))
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
        out = self.draw_overlay(frame)
        self.pub.publish(self.bridge.cv2_to_imgmsg(out, encoding="bgr8"))

    def put_label(self, img, text, x, y, fs=None):
        h, w = img.shape[:2]

        font, thk = cv2.FONT_HERSHEY_SIMPLEX, 2
        fs = fs or max(0.8, 0.0012 * max(w, h))
        (tw, th), base = cv2.getTextSize(text, font, fs, thk)
        pad = 6
        x = max(pad, min(w - tw - pad, x))
        y = max(pad + th, min(h - pad, y))
        cv2.rectangle(img, (x - pad, y - th - pad), (x + tw + pad, y + base + pad), (0, 0, 0), -1)
        cv2.putText(img, text, (x, y), font, fs, (0, 0, 0), thk + 2, cv2.LINE_AA)  # contorno
        cv2.putText(img, text, (x, y), font, fs, (0, 255, 0), thk, cv2.LINE_AA)    # texto

    def get_angle_x(self):
        angle_x = None
        
        # Check if audio has expired
        if hasattr(self, "last_audio_time"):
            now = self.get_clock().now()
            dt = (now - self.last_audio_time).nanoseconds / 1e9
            if dt > 2.0:
                self.last_angle = None
                self.speaker = None

        if self.last_angle and self.fx and self.cx:
            angle_deg = max(-89.9, min(self.last_angle, 89.9))
            angle_rad = math.radians(angle_deg)
            angle_x = int(self.cx + self.fx * math.tan(angle_rad)) # pinhole model
        
        return angle_x

    def draw_overlay(self, frame):
        h, w = frame.shape[:2]
        mid_y = int(h * 0.5)

        angle_x = self.get_angle_x()

        if angle_x:
            angle_x = max(0, min(angle_x, w-1))
            cv2.line(frame, (angle_x, 0), (angle_x, h), (255, 0, 0), 4, cv2.LINE_AA)
            self.put_label(frame, f"{self.last_angle:+.1f} deg", angle_x + 10, mid_y)
        else:
            self.put_label(frame, "No voice", int(w * 0.05), mid_y)

        speaker = self.speaker["name"] if self.speaker else "No Speaker"
        self.put_label(frame, speaker, 10, h-10)
        
        return frame
    
    def on_recognitions(self, msg: FaceRecognitionArray):        
        recognitions = msg.recognitions
        detections = msg.detections

        if len(recognitions) <= 0:
            return
        
        angle_x = self.get_angle_x()
        if angle_x is None or angle_x < 0 or angle_x >= msg.image.width:
            return
        
        best_recog, best_diff = None, float('inf')
        max_pixel_diff = 100
        for recog, det in zip(recognitions, detections):
            det_center_x = det.corner.x + (det.width / 2)
           
            diff = abs(det_center_x - angle_x)
            if diff < best_diff and diff < max_pixel_diff:
                best_diff = diff
                best_recog = recog
        
        if best_recog:
            self.speaker = {
                "id": best_recog.classified_id, 
                "name": best_recog.classified_name
            }


def main(args=None):
    rclpy.init(args=args)
    node = DOAActiveSpeakerNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()