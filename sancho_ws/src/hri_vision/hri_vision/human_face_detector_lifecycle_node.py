import cv2
import rclpy
import time

from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile
from sensor_msgs.msg import Image
from std_msgs.msg import Header
from sancho_msgs.msg import FaceDetection, FaceDetectionArray
from hri_msgs.srv import Detection

from .hri_bridge import HRIBridge
from .detectors import load_detector, BaseDetector


class HumanFaceDetectorLifecycle(LifecycleNode):
    def __init__(self):
        super().__init__("human_face_detector")

        self.declare_parameters(namespace="", parameters=[
            ("image_topic", "/camera/color/image_raw"),
            ("detections_topic", "/face_detections"),
            ("detector_name", "dlib_cnn"),
            ("show_metrics", False),
            ("processing_rate", 10.0)
        ])

        self.detector = None
        self.bridge = HRIBridge()

        self.pub = None
        self.sub = None
        self.timer = None
        self.latest_img = None
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
        self.pub = self.create_lifecycle_publisher(FaceDetectionArray, self.detections_topic, qos)

        self.detection_srv = self.create_service(Detection, "detection", self.detection_service)

        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo...")

        qos = QoSProfile(depth=1)
        self.sub = self.create_subscription(Image, self.image_topic, self.image_callback, qos)
        self.timer = self.create_timer(1.0 / self.processing_rate, self.process_image)

        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo...")

        if self.timer:
            self.timer.cancel()
            self.timer = None

        if self.sub:
            self.destroy_subscription(self.sub)
            self.sub = None

        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando recursos...")

        if self.timer:
            self.timer.cancel()
            self.timer = None

        if self.sub:
            self.destroy_subscription(self.sub)
            self.sub = None

        if self.pub:
            self.destroy_publisher(self.pub)
            self.pub = None

        if self.detection_srv:
            self.destroy_service(self.detection_srv)
            self.detection_srv = None

        return TransitionCallbackReturn.SUCCESS

    def image_callback(self, msg: Image):
        self.latest_img = msg

    def process_image(self):
        if self.latest_img is None:
            return

        start_time = time.time()

        try:
            frame = self.bridge.imgmsg_to_cv2(self.latest_img, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Error con imgmsg_to_cv2: {e}")
            return

        frame_equalized = self.preprocess_frame(frame)
        positions, scores = self.detector.get_faces(frame_equalized)

        msg_array = FaceDetectionArray()
        msg_array.header = Header()
        msg_array.header.stamp = self.latest_img.header.stamp
        msg_array.header.frame_id = self.latest_img.header.frame_id
        msg_array.image = self.latest_img  # <-- añadimos la imagen original

        for (x, y, w, h), score in zip(positions, scores):
            detection = FaceDetection()
            detection.x = float(x)
            detection.y = float(y)
            detection.width = float(w)
            detection.height = float(h)
            detection.confidence = float(score)
            msg_array.detections.append(detection)

        self.pub.publish(msg_array)

        if self.show_metrics:
            elapsed = time.time() - start_time
            self.get_logger().info(f"Detections: {len(positions)} | Tiempo: {elapsed:.3f}s")

    def detection_service(self, request, response):
        start_detection = time.time()

        try:
            frame = self.bridge.imgmsg_to_cv2(request.frame, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Error al convertir imagen del servicio: {e}")
            return response

        frame_equalized = self.preprocess_frame(frame)
        positions, scores = self.detector.get_faces(frame_equalized)
        positions_msg, scores_msg = self.bridge.detector_to_msg(positions, scores)

        response.positions = positions_msg
        response.scores = scores_msg
        response.detection_time = time.time() - start_detection

        if self.show_metrics:
            self.get_logger().info(f"[Servicio] Detecciones: {len(positions)} | Tiempo: {response.detection_time:.3f}s")

        return response

    def preprocess_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        image_bilateral = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
        gray_equalized = cv2.equalizeHist(image_bilateral)
        frame_ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        frame_ycrcb[:, :, 0] = gray_equalized
        return cv2.cvtColor(frame_ycrcb, cv2.COLOR_YCrCb2BGR)


def main(args=None):
    rclpy.init(args=args)
    node = HumanFaceDetectorLifecycle()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
