import cv2
from mtcnn.mtcnn import MTCNN

from .base_detector import BaseDetector


class MTCNNDetector(BaseDetector):

    def __init__(self):
        self.faceDetector = MTCNN()

    def get_faces(self, frame, verbose=False):
        frameCopy = frame.copy()
        faces = self.faceDetector.detect_faces(frame)

        scores = []
        cuttedFaces = []
        facePositions = []
        for face in faces:
            x, y, w, h = face['box']
            cuttedFaces.append(frame[y:(y+h), x:(x+w)])
            facePositions.append((x, y, w, h))
            scores.append(10)

            if verbose:
                cv2.rectangle(frameCopy, (x, y), (x + w, y + h), (255, 0, 0), 2)

        if verbose:
            cv2.imshow('Face Detection', frameCopy)

        return facePositions, scores