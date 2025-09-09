from deepface import DeepFace
import numpy as np
from .base_encoder import BaseEncoder

class SFaceEncoder(BaseEncoder):
    def __init__(self):
        self.model_name = 'SFace'

    def encode_face(self, face):
        embedding_objs = DeepFace.represent(
            img_path=face,
            model_name=self.model_name,
            detector_backend='skip',
            enforce_detection=False
        )
        
        embeddings = np.array(embedding_objs[0]["embedding"])
        return embeddings / np.linalg.norm(embeddings)
