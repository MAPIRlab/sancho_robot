from enum import Enum

from .base_detector import BaseDetector
from .factory import load_detector


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
