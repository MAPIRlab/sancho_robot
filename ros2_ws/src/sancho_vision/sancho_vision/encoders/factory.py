import importlib
from .base_encoder import BaseEncoder

def load_encoder(encoder_name: str) -> BaseEncoder:
    encoder_map = {
        "efficientface": "efficientfacev2_encoder.EfficientFaceV2SEncoder",
        "facenet": "facenet_encoder.FaceNetEncoder",
        "openface": "openface_encoder.OpenFaceEncoder",
        "arcface": "arcface_encoder.ArcFaceEncoder",
        "sface": "sface_encoder.SFaceEncoder",
        "vggface": "vggface_encoder.VGGFaceEncoder",
        "dino": "dinov2_encoder.DINOV2Encoder",
    }

    try:
        module_class = encoder_map[encoder_name]
        module_name, class_name = module_class.rsplit(".", 1)
        module = importlib.import_module(f".{module_name}", package="sancho_vision.encoders")
        encoder_class = getattr(module, class_name)
        return encoder_class()
    except KeyError:
        raise ValueError(f"Reconocedor '{encoder_name}' no reconocido")
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar el reconocedor '{encoder_name}': {e}")
