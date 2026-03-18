#!/usr/bin/env python3

import copy

import cv2 as cv
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub


def load_model(model_url):
    """Carga el modelo MoveNet desde TensorFlow Hub."""
    try:
        model = hub.load(model_url).signatures["serving_default"]
        return model
    except Exception as e:
        raise RuntimeError(f"Error al cargar el modelo: {e}")


def preprocess_image(image, input_size):
    """Redimensiona y preprocesa la imagen para el modelo.
    Retorna la imagen preprocesada, ancho y alto originales.
    """
    image_height, image_width = image.shape[:2]
    input_image = cv.resize(image, (input_size, input_size))
    input_image = cv.cvtColor(input_image, cv.COLOR_BGR2RGB)
    input_image = input_image.reshape(-1, input_size, input_size, 3)
    input_image = tf.cast(input_image, dtype=tf.int32)
    return input_image, image_width, image_height


def run_inference_on_image(image, input_size, model):
    """Ejecuta el modelo sobre la imagen preprocesada.
    Retorna dos listas: una de keypoints y otra de scores.
    """
    input_image, image_width, image_height = preprocess_image(image, input_size)
    outputs = model(input_image)
    keypoints_with_scores = outputs["output_0"].numpy().squeeze()
    keypoints_list = []
    scores_list = []
    for kp_with_score in keypoints_with_scores:
        keypoints = []
        scores = []
        for i in range(17):  # Se asume que se detectan 17 keypoints
            x = int(image_width * kp_with_score[i * 3 + 1])
            y = int(image_height * kp_with_score[i * 3 + 0])
            score = kp_with_score[i * 3 + 2]
            keypoints.append((x, y))
            scores.append(score)
        keypoints_list.append(keypoints)
        scores_list.append(scores)
    return keypoints_list, scores_list


def process_detections(
    keypoints_list, scores_list, keypoint_score_threshold, min_keypoints
):
    """Filtra las detecciones descartando aquellas con menos de 'min_keypoints' válidos."""
    valid_detections = []
    for keypoints, scores in zip(keypoints_list, scores_list, strict=False):
        count_valid = sum([1 for score in scores if score > keypoint_score_threshold])
        if count_valid >= min_keypoints:
            valid_detections.append((keypoints, scores))
    return valid_detections


def get_depth_value(x, y, depth_image, window_size=3):
    """Calcula la profundidad robusta promediando en una ventana centrada en (x,y).
    Se ignoran valores cero.
    """
    half_w = window_size // 2
    h, w = depth_image.shape
    x_min = max(x - half_w, 0)
    x_max = min(x + half_w + 1, w)
    y_min = max(y - half_w, 0)
    y_max = min(y + half_w + 1, h)
    patch = depth_image[y_min:y_max, x_min:x_max]
    valid = patch[patch > 0]
    if valid.size == 0:
        return 0.0

    return float(np.mean(valid)) / 1000.0  # Convertir a metros (mm -> m)


def convert_2d_to_3d(u, v, depth_value, camera_info):
    """Convierte un punto 2D (u,v) a 3D usando el modelo de cámara pinhole."""
    if camera_info is None:
        return (0.0, 0.0, 0.0)
    K = camera_info.k  # Matriz de cámara (lista de 9 elementos)
    fx = K[0]
    fy = K[4]
    cx = K[2]
    cy = K[5]
    try:
        X = (u - cx) * depth_value / fx
        Y = (v - cy) * depth_value / fy
        Z = depth_value
        return (X, Y, Z)
    except Exception:
        return (0.0, 0.0, 0.0)


def draw_skeleton(image, keypoints, scores, keypoint_score_threshold):
    """Dibuja el esqueleto sobre la imagen usando las conexiones predefinidas."""
    connections = [
        (0, 1),
        (0, 2),
        (1, 3),
        (2, 4),
        (0, 5),
        (0, 6),
        (5, 6),
        (5, 7),
        (7, 9),
        (6, 8),
        (8, 10),
        (5, 11),
        (6, 12),
        (11, 12),
        (11, 13),
        (13, 15),
        (12, 14),
        (14, 16),
    ]
    annotated = copy.deepcopy(image)
    for i, j in connections:
        if (
            scores[i] > keypoint_score_threshold
            and scores[j] > keypoint_score_threshold
        ):
            pt1 = keypoints[i]
            pt2 = keypoints[j]
            cv.line(annotated, pt1, pt2, (0, 0, 0), 2)
            cv.line(annotated, pt1, pt2, (255, 255, 255), 4)
    for pt, score in zip(keypoints, scores, strict=False):
        if score > keypoint_score_threshold:
            cv.circle(annotated, pt, 6, (0, 0, 0), -1)
            cv.circle(annotated, pt, 3, (255, 255, 255), -1)
    return annotated


def annotate_depth(depth_image):
    """Genera una imagen pseudo-coloreada a partir de la imagen de profundidad."""
    try:
        depth_normalized = cv.normalize(depth_image, None, 0, 255, cv.NORM_MINMAX)
        depth_normalized = np.uint8(depth_normalized)
        depth_colored = cv.applyColorMap(depth_normalized, cv.COLORMAP_JET)
        return depth_colored
    except Exception:
        return depth_image
