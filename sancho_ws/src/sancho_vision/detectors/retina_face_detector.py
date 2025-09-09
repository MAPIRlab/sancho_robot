import cv2
import numpy as np
import retinaface.RetinaFace as retinaface
from .base_detector import BaseDetector

class RetinaFaceDetector(BaseDetector):
    def __init__(self):
        self.model = retinaface.build_model()

    def get_faces(self, frame, verbose=False):
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) 
        detections = retinaface.detect_faces(frame_bgr, model=self.model)

        face_positions = []
        face_scores = []

        for face_data in detections.values():
            x1, y1, x2, y2 = face_data["facial_area"]
            score = face_data.get("score", 1.0)
            x, y = int(x1), int(y1)
            w, h = int(x2 - x1), int(y2 - y1)
            face_positions.append((x, y, w, h))
            face_scores.append(float(score))

            if verbose:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        if verbose and face_positions:
            cv2.imshow("RetinaFace Detection", frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return face_positions, face_scores
