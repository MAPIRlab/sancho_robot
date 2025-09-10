import cv2
import rclpy

from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from geometry_msgs.msg import Point
from sancho_msgs.msg import FaceDetection, FaceDetectionArray
from hri_msgs.srv import Detection

from .hri_bridge import HRIBridge
from .detectors import load_detector, BaseDetector


class HumanFaceDetectorLifecycleNode(LifecycleNode):
    def __init__(self):
        super().__init__("human_face_detector")

        self.declare_parameters(namespace="", parameters=[
            ("image_topic", "/camera/color/image_raw"),
            ("detections_topic", "/face_detections"),
            ("detector_name", "dlib_cnn"),
            ("show_metrics", False),
            ("processing_rate", 10.0)
        ])

        self.bridge = HRIBridge()

        self.detector = None

        self.sub_camera = None
        self.pub_dets = None

        self.detection_srv = None

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        self.image_topic = self.get_parameter("image_topic").value
        self.detections_topic = self.get_parameter("detections_topic").value
        self.detector_name = self.get_parameter("detector_name").value
        self.show_metrics = self.get_parameter("show_metrics").value
        self.processing_rate = self.get_parameter("processing_rate").value

        try:
            self.detector: BaseDetector = load_detector(self.detector_name)
            self.get_logger().info(f"Detector seleccionado: {self.detector_name}")
        except Exception as e:
            self.get_logger().error(f"Error cargando el detector: {e}")
            return TransitionCallbackReturn.FAILURE

        qos = QoSProfile(depth=10)
        self.pub_dets = self.create_lifecycle_publisher(FaceDetectionArray, self.detections_topic, qos)

        self.detection_srv = self.create_service(Detection, "detection", self.detection_service)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo de detección...")

        qos = QoSProfile(depth=1)
        self.sub_camera = self.create_subscription(Image, self.image_topic, self.image_callback, qos)

        self.latest_img = None
        self.spin_timer = self.create_timer(1.0 / self.processing_rate, self.do_detection)

        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo de detección...")

        if self.spin_timer:
            self.spin_timer.cancel()
            self.spin_timer = None

        if self.sub_camera:
            self.destroy_subscription(self.sub_camera)
            self.sub_camera = None

        return TransitionCallbackReturn.SUCCESS

    def image_callback(self, msg: Image):
        self.latest_img = msg

    def do_detection(self):
        if self.latest_img is None:
            return

        msg = self.latest_img
        positions, confidences = self.detect(msg)

        msg_array = FaceDetectionArray()
        msg_array.header = Header()
        msg_array.header.stamp = msg.header.stamp
        msg_array.header.frame_id = msg.header.frame_id
        msg_array.image = msg  # <-- añadimos la imagen original

        for (x, y, w, h), confidence in zip(positions, confidences):
            detection = FaceDetection()
            
            detection.corner = Point(x=float(x), y=float(y), z=0.0)
            detection.width = float(w)
            detection.height = float(h)
            detection.confidence = float(confidence)
            msg_array.detections.append(detection)

        self.pub_dets.publish(msg_array)

    def detection_service(self, request, response):
        positions, confidences = self.detect(request.image)

        response.positions, response.scores = self.bridge.detector_to_msg(positions, confidences)

        return response

    def detect(self, frame):
        if isinstance(frame, Image):
            frame = self.bridge.imgmsg_to_cv2(frame, "bgr8")

        frame_equalized = self.preprocess_frame(frame)
        positions, confidences = self.detector.get_faces(frame_equalized)
        
        return positions, confidences

    def preprocess_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        image_bilateral = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
        gray_equalized = cv2.equalizeHist(image_bilateral)
        frame_ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        frame_ycrcb[:, :, 0] = gray_equalized
        return cv2.cvtColor(frame_ycrcb, cv2.COLOR_YCrCb2BGR)


def main(args=None):
    rclpy.init(args=args)

    lifecycle_node = HumanFaceDetectorLifecycleNode()

    rclpy.spin(lifecycle_node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
