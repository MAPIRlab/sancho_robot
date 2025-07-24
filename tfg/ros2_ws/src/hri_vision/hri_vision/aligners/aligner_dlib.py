import os
import dlib
import cv2

face_landmark_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models/shape_predictor_68_face_landmarks.dat")
face_landmark_predictor = dlib.shape_predictor(face_landmark_path)

def align_face(frame, face_position):
    """Aligns the face, using dlib landmarks

    Args:
        frame (Image): Image containing the face
        face_position (Array: int): Array with the x and y coordinates and height and width of a rectangle containing the face

    Returns:
        face_aligned (Image): The face at face_position aligned
    """

    gray = cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2GRAY)
    box = dlib.rectangle(face_position[0], face_position[1], face_position[0] + face_position[2] - 1,
                         face_position[1] + face_position[3] - 1)
    landmarks = face_landmark_predictor(gray, box)

    face_aligned = dlib.get_face_chip(frame, landmarks, size=256, padding=0.5)

    return face_aligned
