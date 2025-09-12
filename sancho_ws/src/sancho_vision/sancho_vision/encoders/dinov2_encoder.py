import os
import torch
import numpy as np
from PIL import Image
import torchvision.transforms as T
from dotenv import load_dotenv
from huggingface_hub import login
from transformers import AutoImageProcessor, AutoModel
from .base_encoder import BaseEncoder


class DinoV2Encoder(BaseEncoder):
    def __init__(self):
        load_dotenv()
        hf_token = os.getenv("HUGGING_FACE_API_KEY")

        if hf_token:
            login(token=hf_token)
        else:
            raise EnvironmentError("HUGGING_FACE_API_KEY no encontrada en .env")

        model_name = "facebook/dinov2-base"  # Salida esperada: 768D
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        self.processor = AutoImageProcessor.from_pretrained(model_name, token=hf_token)
        self.model = AutoModel.from_pretrained(model_name, token=hf_token).to(self.device)

        # Tamaño fijo esperado por DINOv2 base
        self.target_size = (518, 518)

        # Transformación manual, sin usar processor.resize/random_crop
        self.transform = T.Compose([
            T.Resize(self.target_size),
            T.CenterCrop(self.target_size),
            T.ToTensor(),
            T.Normalize(mean=self.processor.image_mean, std=self.processor.image_std)
        ])

    def encode_face(self, face):
        if isinstance(face, np.ndarray):
            face = Image.fromarray(face)

        image = self.transform(face).unsqueeze(0).to(self.device)

        with torch.no_grad():
            outputs = self.model(pixel_values=image)
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()

        return embedding / np.linalg.norm(embedding)
