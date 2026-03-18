import cv2
import tempfile
import os
from yolov8face import get_bbox
from .base_detector import BaseDetector

class YOLOv8FaceDetector(BaseDetector):

    def get_faces(self, frame, verbose=False):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            temp_path = tmp.name
            cv2.imwrite(temp_path, frame)

        try:
            bboxes = list(get_bbox(temp_path).cpu().numpy().tolist())
        finally:
            os.remove(temp_path)

        face_positions = []
        scores = []

        for x1, y1, x2, y2 in bboxes or []:
            x, y = int(x1), int(y1)
            w, h = int(x2 - x1), int(y2 - y1)
            face_positions.append((x, y, w, h))
            scores.append(1.0)

        if verbose and face_positions:
            disp = frame.copy()
            for (x, y, w, h) in face_positions:
                cv2.rectangle(disp, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.imshow("YOLOv8-Face Detection", disp)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return face_positions, scores
