import dlib
import cv2

from .base_detector import BaseDetector


class DLIBCNNDetector(BaseDetector):

    def __init__(self):
        self.cnn_face_detector = dlib.cnn_face_detection_model_v1('/home/ubuntu/tfg/ros2_ws/src/hri_vision/hri_vision/models/mmod_human_face_detector.dat')

    def get_faces(self, frame, verbose=False):
        frame_copy = frame.copy()
        faces = self.cnn_face_detector(frame, 1)

        face_positions = []
        scores = []
        for face in faces:
            rect = face.rect
            x, y, w, h = (rect.left(), rect.top(), rect.width(), rect.height())
            face_positions.append((x, y, w, h))
            scores.append(face.confidence)

            if verbose:
                cv2.rectangle(frame_copy, (x, y), (x + w, y + h), (255, 0, 0), 2)

        if verbose:
            cv2.imshow('Face Detection', frame_copy)

        return face_positions, scores
