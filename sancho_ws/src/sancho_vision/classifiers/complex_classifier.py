import os
import cv2
import base64

from ..api.utils import normalized_cosine_similarity_distance
from ..database.faceprints_database import FaceprintsDatabase


class ComplexClassifier:

    def __init__(self, db_mode="save"):
        '''Inits classifier'''

        self.db_mode = db_mode
        self.db_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "database/faceprints_db.json"))
        self.db = FaceprintsDatabase(self.db_path, self.db_mode)

        self.print_people()

    def classify_face(self, new_features):
        '''Given a feature vector, gives the closest class.
        
        Args:
            new_features (Array: float): Feature vector.
        
        Returns:
            closest_faceprint (dict): The faceprint.
            closes_distance (float): The normalized cosine distance to the closest_class.
            position (int): The position of the vector in the array of vectors of the class that
                was the closest to the given vector.
        '''

        closest_faceprint = None
        closest_distance = 0
        position = 0
        for faceprint in self.db.get_all():
            feature_list = faceprint["features"]

            for i in range(0, len(feature_list)):
                distance = normalized_cosine_similarity_distance(new_features, feature_list[i])

                if distance > closest_distance:
                    closest_distance = distance
                    closest_faceprint = faceprint
                    position = i

        return closest_faceprint, closest_distance, position

    def refine_class(self, class_id, features, position):
        '''Makes a certain feature vector more precise by averaging with a new feature vector.

        Args:
            class_id (str): The class id.
            features (Array: float): The new feature vector.
            position (int): The position of the known feature vector we want to make more precise.
        '''

        faceprint = self.db.get_by_id(class_id)
   
        new_size = faceprint["size"][position] + 1
        faceprint["size"][position] = new_size

        faceprint["features"][position] = [(x * (new_size - 1) + y) / new_size for x, y in 
                                             zip(faceprint["features"][position], features)]
        
        self.db.update(class_id, faceprint)

        result = 1
        message = "La clase con id " + class_id + " ha sido refinada"

        return result, message

    def add_features(self, class_id, features):
        '''Adds a new feature vector to the array of vectors that describes a class.
        
        Args:
            class_id (str): The class id.
            features (Array: float): The new feature vector.
        '''
        
        faceprint = self.db.get_by_id(class_id)

        faceprint["features"].append(features)
        faceprint["size"].append(1)

        self.db.update(class_id, faceprint)
        
        result = 1
        message = ("La clase con id " + class_id + " ahora tiene " + 
            str(len(faceprint["features"])) + " vectores de características independientes.")

        self.db.save()
        return result, message

    def add_class(self, class_name, features, face, score):
        '''Adds a new class with a unique feature vector.

        Args:
            class_name (str): The class.
            features (Array: float): The feature vector.
            face (str): Base64 face image.
            score (float): Score of the detection
        '''

        faceprint = self.db.add(class_name, features, face, score)

        result = 1
        message = faceprint["id"]

        self.db.save()
        return result, message

    def rename_class(self, class_id, new_name):
        '''Renames a class.

        Args:
            class_id (str): The class id.
            new_name (str): The new class name.
        '''

        self.db.update(class_id, { "name": new_name })
    
        result = 1
        message = "La clase con id " + class_id + " ha sido renombrada a " + new_name

        self.db.save()
        return result, message

    def delete_class(self, class_id):
        '''Removes a class.
        
        Args:
            class_id (str): The class id.
        '''
    
        self.db.remove(class_id)

        result = 1
        message = "La clase con id " + class_id + " ha sido eliminada correctamente"

        self.db.save()
        return result, message
    
    def save_face(self, class_id, face, face_score):
        '''Saves face image as a representation of the class

        Args:
            class_id (str): The class id.
            face (cv2-Image): Cropped face image.
            face_score (float): Score of the detection.
        '''

        faceprint = self.db.get_by_id(class_id)
        is_best_face = faceprint is not None and face_score > faceprint.get("face_score", 0)

        if is_best_face:
            target_size = (128, 128)
            resized = face#cv2.resize(face, target_size, interpolation=cv2.INTER_AREA)

            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
            _, jpeg = cv2.imencode('.jpg', resized, encode_param)

            face_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
            self.db.update(class_id, { 
                "face": face_base64, 
                "face_score": face_score 
            })
        
            self.db.save()
            
        return is_best_face
    
    def print_people(self):
        '''Prints all known people'''

        print("Known people:")
        for faceprint in self.db.get_all():
            print(f"- [{faceprint['id']}] {faceprint['name']}")