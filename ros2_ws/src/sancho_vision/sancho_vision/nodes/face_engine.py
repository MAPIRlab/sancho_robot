import numpy as np
from sancho_vision.detectors import load_detector
from sancho_vision.encoders import load_encoder
from sancho_vision.classifiers.complex_classifier import ComplexClassifier
from sancho_vision.aligners.aligner_dlib import align_face

class FaceEngine:
    def __init__(self, detector_name: str, encoder_name: str):
        self.detector = load_detector(detector_name)
        self.encoder = load_encoder(encoder_name)
        self.classifier = ComplexClassifier('save')

    def process_body_crop(self, frame_raw: np.ndarray, x: int, y: int, w: int, h: int, head_fraction: float):
        """
        Extrae la cabeza del bounding box del cuerpo, la alinea, codifica y clasifica.
        Retorna un diccionario con los resultados, o None si no hay una cara válida.
        """
        # 1. Recorte superior
        y_margin, x_margin = int(h * 0.2), int(w * 0.2)
        head_h = int(h * head_fraction)

        y1, y2 = max(0, y - y_margin), min(frame_raw.shape[0], y + head_h)
        x1, x2 = max(0, x - x_margin), min(frame_raw.shape[1], x + w + x_margin)
        
        if y2 <= y1 or x2 <= x1: return None
        
        crop = frame_raw[y1:y2, x1:x2]
        if crop.shape[0] < 40 or crop.shape[1] < 40:
            return None

        # 2. Detección
        positions, confidences = self.detector.get_faces(crop)
        if not positions:
            return None

        idx = int(np.argmax(confidences))
        best_face, best_conf = positions[idx], float(confidences[idx])
        
        if best_conf < 0.85:
            return None

        # 3. Coordenadas absolutas
        if hasattr(best_face, 'left'):
            abs_pos = [best_face.left() + x1, best_face.top() + y1, best_face.width(), best_face.height()]
        else:
            abs_pos = [best_face[0] + x1, best_face[1] + y1, best_face[2], best_face[3]]

        # 4. Alineación
        face_aligned = align_face(frame_raw, abs_pos)
        if face_aligned is None:
            return None

        # 5. Codificación y Clasificación
        features = self.encoder.encode_face(face_aligned)
        faceprint, distance, pos = self.classifier.classify_face(features)

        return {
            'face_aligned': face_aligned,
            'features': features,
            'faceprint': faceprint,
            'distance': distance,
            'pos': pos
        }