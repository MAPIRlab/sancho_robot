import dlib
import cv2

from .base_detector import BaseDetector


class DLIBFrontalDetector(BaseDetector):

    def __init__(self):
        self.face_detector = dlib.get_frontal_face_detector()

    def get_faces(self, frame, verbose=False):
        frame_copy = frame.copy()
        faces, scores, idx = self.face_detector.run(frame, 1, 0)

        face_positions = []
        for face in faces:
            x, y, w, h = (face.left(), face.top(), face.width(), face.height())
            face_positions.append((x, y, w, h))

            if verbose:
                cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (255, 0, 0), 2)

        if verbose:
            cv2.imshow('Face Detection', frame_copy)

        return face_positions, scores