import cv2
import rclpy
import time
from enum import Enum

from rclpy.node import Node
from hri_msgs.srv import Detection

from .hri_bridge import HRIBridge
from .detectors import ( BaseDetector,
    CV2Detector, DLIBCNNDetector, DLIBFrontalDetector,
    MTCNNDetector, InsightFaceDetector,
    RetinaFaceDetector, YOLOv5FaceDetector, YOLOv8FaceDetector
)


class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class DetectorType(SmartStrEnum):
    CV2 = "cv2"
    DLIB_CNN = "dlib_cnn"
    DLIB_FRONTAL = "dlib_frontal"
    MTCNN = "mtcnn"
    YOLOV5 = "yolov5"
    YOLOV8 = "yolov8"
    RETINAFACE = "retinaface"
    INSIGHTFACE = "insightface"


DETECTOR_CLASS_MAP = {
    DetectorType.CV2: CV2Detector,
    DetectorType.DLIB_CNN: DLIBCNNDetector,
    DetectorType.DLIB_FRONTAL: DLIBFrontalDetector,
    DetectorType.MTCNN: MTCNNDetector,
    DetectorType.YOLOV5: YOLOv5FaceDetector,
    DetectorType.YOLOV8: YOLOv8FaceDetector,
    DetectorType.RETINAFACE: RetinaFaceDetector,
    DetectorType.INSIGHTFACE: InsightFaceDetector,
}


class HumanFaceDetector(Node):

    def __init__(self):
        super().__init__("human_face_detector")

        self.show_metrics = self.declare_parameter("show_metrics", False).value
        detector_name = self.declare_parameter("detector_name", DetectorType.DLIB_CNN).value.lower()

        try:
            detector_type = DetectorType(detector_name)
        except ValueError:
            self.get_logger().warn(f"Detector '{detector_name}' no reconocido. Usando 'insightface' por defecto.")
            detector_type = DetectorType.INSIGHTFACE

        self.get_logger().info(f"Detector seleccionado: {detector_type}")
        self.detector: BaseDetector = DETECTOR_CLASS_MAP[detector_type]()

        self.detection_service = self.create_service(Detection, "detection", self.detection)

        self.last_detection_time = 0
        self.br = HRIBridge()

    def detection(self, request, response):
        start_detection = time.time()

        frame = self.br.imgmsg_to_cv2(request.frame, "bgr8")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
  
        image_bilateral = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
        gray_equalized = cv2.equalizeHist(image_bilateral) 
        
        frame_ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        frame_ycrcb[:, :, 0] = gray_equalized
        frame_equalized = cv2.cvtColor(frame_ycrcb, cv2.COLOR_YCrCb2BGR)

        if self.detector:
            positions, scores = self.detector.get_faces(frame_equalized)
            positions_msg, scores_msg = self.br.detector_to_msg(positions, scores)

            if len(positions_msg) > 0:
                self.get_logger().info("Faces detected: " + str(len(positions_msg)))

            response.positions = positions_msg
            response.scores = scores_msg

        detection_time = time.time() - start_detection
        response.detection_time = detection_time
        if self.show_metrics:
            self.get_logger().info("Detection time: " + str(detection_time))

        return response


def main(args=None):
    rclpy.init(args=args)

    node = HumanFaceDetector()
    rclpy.spin(node)

    rclpy.shutdown()
