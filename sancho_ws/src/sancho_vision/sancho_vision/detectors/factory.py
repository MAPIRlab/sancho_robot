import importlib
from .base_detector import BaseDetector

def load_detector(detector_name: str) -> BaseDetector:
    detector_map = {
        "cv2": "cv2_detector.CV2Detector",
        "dlib_cnn": "dlib_cnn_detector.DLIBCNNDetector",
        "dlib_frontal": "dlib_frontal_detector.DLIBFrontalDetector",
        "mtcnn": "mtcnn_detector.MTCNNDetector",
        "yolov5": "yolo_v5_face_detector.YOLOv5FaceDetector",
        "yolov8": "yolo_v8_face_detector.YOLOv8FaceDetector",
        "retinaface": "retina_face_detector.RetinaFaceDetector",
        "insightface": "insight_face_detector.InsightFaceDetector",
    }

    try:
        module_class = detector_map[detector_name]
        module_name, class_name = module_class.rsplit(".", 1)
        module = importlib.import_module(f".{module_name}", package="sancho_vision.detectors")
        detector_class = getattr(module, class_name)
        return detector_class()
    except KeyError:
        raise ValueError(f"Detector '{detector_name}' no reconocido")
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar el detector '{detector_name}': {e}")
