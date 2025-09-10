import cv2
import time

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from ros2web_msgs.srv import R2WSubscribe


class Video(Node):

    def __init__(self, path):
        super().__init__("video")

        self.get_logger().info(f"Trying to open video on path {path}")
        self.video = cv2.VideoCapture(path)
        self.publisher = self.create_publisher(Image, "camera/color/image_raw", 1)

        self.subscribe_client = self.create_client(R2WSubscribe, "ros2web/subscribe")
        while not self.subscribe_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warning("ROS2WEB Subscribe Service not available, waiting...")

        self.bridge = CvBridge()

        self.spin()

    def subscribe_request(self, topic, name=""):
        subscribe_request = R2WSubscribe.Request()
        subscribe_request.topic = topic
        subscribe_request.name = name

        future_subscribe = self.subscribe_client.call_async(subscribe_request)
        rclpy.spin_until_future_complete(self, future_subscribe)
        result_subscribe = future_subscribe.result()

        return result_subscribe.value

    def spin(self):
        fps = self.video.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            self.get_logger().warn("FPS reportado como 0. Usando valor por defecto: 30")
            fps = 30.0
        else:
            self.get_logger().info(f"FPS: {fps}")

        frame_duration = 1.0 / fps
        first_frame = True
        frame_idx = 0
        start_time = time.time()

        while rclpy.ok():
            ret, frame = self.video.read()

            if not ret:
                self.get_logger().info("El video ha terminado, reiniciando.")
                self.video.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx = 0
                start_time = time.time()
                continue

            if first_frame:
                first_frame = False
                self.get_logger().info("Video Node initializated succesfully")

            self.publisher.publish(self.bridge.cv2_to_imgmsg(frame, "bgr8"))

            target_time = start_time + frame_idx * frame_duration
            now = time.time()
            sleep_time = target_time - now
            if sleep_time > 0:
                time.sleep(sleep_time)

            frame_idx += 1

        self.video.release()


def main(args=None):
    rclpy.init(args=args)

    video = Video("../sandbox/video.mp4")

    rclpy.spin(video)
    rclpy.shutdown()
