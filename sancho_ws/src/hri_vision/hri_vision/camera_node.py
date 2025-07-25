import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

from cv_bridge import CvBridge


class Camera(Node):

    def __init__(self):
        super().__init__("camera")

        self.get_logger().info("Trying to start camera on index 0")
        self.camera = cv2.VideoCapture(0)

        self.publisher = self.create_publisher(Image, "camera/color/image_raw", 1)
        self.bridge = CvBridge()

        self.spin()

    def spin(self):
        first_frame = True
        while True:
            ret, frame = self.camera.read()

            if not ret:
                break
            
            if first_frame:
                first_frame = False
                self.get_logger().info("Camera Node initializated succesfully")
            
            self.publisher.publish(self.bridge.cv2_to_imgmsg(frame, "bgr8"))
            cv2.waitKey(1)

        self.camera.release()

def main(args=None):
    rclpy.init(args=args)

    camera = Camera()

    rclpy.spin(camera)
    rclpy.shutdown()