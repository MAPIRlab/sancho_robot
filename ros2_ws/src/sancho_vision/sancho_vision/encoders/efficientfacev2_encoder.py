import numpy as np
import cv2
import tensorflow as tf
# This import is required even if not called directly, as it registers custom layers
import keras_cv_attention_models 
from .base_encoder import BaseEncoder
from ament_index_python.packages import get_package_share_directory
import os

class EfficientFaceV2SEncoder(BaseEncoder):
    def __init__(self):
        # Obtener la ruta dinámica del paquete instalado
        package_share = get_package_share_directory('sancho_vision')
        model_path = os.path.join(package_share, 'models', 'EfficientFaceV2S.h5')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"No se encontró el modelo en: {model_path}")

        self.model = tf.keras.models.load_model(model_path, compile=False)

    def encode_face(self, face):
        # 1. Standardize input to 112x112
        face = cv2.resize(face, (112, 112))
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        
        # 2. Normalize pixels and add batch dimension
        face_input = face.astype('float32') / 255.0
        face_input = np.expand_dims(face_input, axis=0)

        # 3. Get 512-d embedding
        embedding = self.model.predict(face_input, verbose=0).flatten()
        
        # 4. L2 Normalize for cosine similarity
        return embedding / np.linalg.norm(embedding)