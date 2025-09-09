import re
import cv2
import base64
import numpy as np

from std_msgs.msg import String
from cv_bridge import CvBridge

from hri_msgs.msg import FacePosition


class HRIBridge:

    def __init__(self):
        self.br = CvBridge()

    def imgmsg_to_cv2(self, img_msg, desired_encoding="passthrough"):
        """Transforms an Image in ROS2 format to cv2

        Args:
            img_msg (Image-ROS2): The image in ROS2 format
            desired_encoding (str): Encoding of the image

        Returns:
            image (Image-CV2): The image in CV2 format
        """

        image = self.br.imgmsg_to_cv2(img_msg, desired_encoding)

        return image

    def cv2_to_imgmsg(self, cvim, encoding="passthrough"):
        """Transforms an Image in cv2 format to ROS2

        Args:
            cvim (Image-CV2): The image in ROS2 format
            desired_encoding (str): Encoding of the image

        Returns:
            img_msg (Image-ROS2): The image in CV2 format
        """

        img_msg = self.br.cv2_to_imgmsg(cvim, encoding)

        return img_msg

    def cv2_to_base64(self, image, quality=50): #ros2utils
        """Transforms an Image in cv2 format to base64 from JPEG
        
        Args:
            image (Image-CV2): The image
            quality (int): The quality of the JPEG encode
        
        Returns:
            image_base64 (str): The base64 of the image
        """

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, jpeg = cv2.imencode('.jpg', image, encode_param)
        image_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')

        return image_base64

    def base64_to_cv2(self, image_base64):
        """Transforms an base64 from JPEG format to Image in cv2
        
        Args:
            image (str): The base64 of the image
            quality (int): The quality of the JPEG encode
        
        Returns:
            image_base64 (Image-CV2): The image
        """

        match = re.match(r"data:image/[^;]+;base64,(.*)", image_base64)
        if not match:
            raise ValueError("Formato base64 inválido o no es una imagen válida.")
        
        image_data = base64.b64decode(match.group(1))
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("No se pudo decodificar la imagen.")
        return img

    def detector_to_msg(self, positions, scores):
        """Transforms detector service response to ROS2 msgs format

        Args:
            positions (int[4][]): Array of array of 4 elements that determine the square in which the face is
            scores (float[]): Array of scores of the detected faces in the same order of the positions

        Returns:
            positions_msg (FacePosition[]): positions transformed to ROS2 format
            scores_msg (int[]): positions in ROS2 format
        """

        positions_msg = []
        for x, y, w, h in positions:
            pos = FacePosition()
            pos.x = int(x)
            pos.y = int(y)
            pos.w = int(w)
            pos.h = int(h)
            positions_msg.append(pos)

        scores_msg = scores

        return positions_msg, scores_msg

    def msg_to_detector(self, positions_msg, scores_msg):
        """Transforms detector service response to normal format

        Args:
            positions_msg (FacePosition[]): positions in ROS2 format
            scores_msg (int[]): positions in ROS2 format

        Returns:
            positions (int[4][]): Array of array of 4 elements that determine the square in which the face is
            scores (float[]): Array of scores of the detected faces in the same order of the positions
        """

        positions = []
        for pos in positions_msg:
            positions.append([pos.x, pos.y, pos.w, pos.h])

        scores = scores_msg

        return positions, scores

    def recognizer_to_msg(self, face_aligned, features, classified_name, distance, pos):
        """Transforms recognizer service response to ROS2 format

        Args:
            face_aligned (Image): The face of the person recognized aligned horizontally
            features (float[]): Features vector
            classified_name (str): The class (name) of the face recognized
            distance (float): Score of the recognition
            pos (int): Number of the vector inside the class that has been used to classify

        Returns:
            face_aligned_msg (Image-ROS2): face_aligned in ROS2 format
            features_msg (float[]): features in ROS2 format
            classified_name:msg (String): classified in ROS2 format
            distance_msg (float): distance in ROS2 format
            pos_msg (int): pos in ROS2 format
        """

        face_aligned_msg = self.cv2_to_imgmsg(face_aligned, "bgr8")
        features_msg = [float(feature) for feature in features]
        classified_name_msg = str(classified_name)
        distance_msg = float(distance)
        pos_msg = pos

        return face_aligned_msg, features_msg, classified_name_msg, distance_msg, pos_msg

    def msg_to_recognizer(self, face_aligned_msg, features_msg, classified_name_msg, distance_msg, pos_msg):
        """Transforms recognizer service response to ROS2 format

        Args:
            face_aligned_msg (Image-ROS2): face_aligned in ROS2 format
            features_msg (float[]): features in ROS2 format
            classified_name_msg (String): classified in ROS2 format
            distance_msg (float): distance in ROS2 format
            pos_msg (int): pos in ROS2 format

        Returns:
            face_aligned (Image): The face of the person recognized aligned horizontally
            features (float[]): Features vector
            classified_name (str): The class (name) of the face recognized
            distance (float): Score of the recognition
            pos (int): Number of the vector inside the class that has been used to classify
        """

        face_aligned = self.imgmsg_to_cv2(face_aligned_msg, "bgr8")
        features = features_msg.tolist()
        classified_name = classified_name_msg
        distance = distance_msg
        pos = pos_msg

        return face_aligned, features, classified_name, distance, pos
