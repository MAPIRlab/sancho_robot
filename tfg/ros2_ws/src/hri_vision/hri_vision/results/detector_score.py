import json
import os

def procesar_resultados(path_json):
    path = os.path.join(os.path.dirname(__file__), path_json)
    with open(path) as f:
        data = json.load(f)

    max_time = max(v["avg_inference_time"] for v in data.values())

    filas = []
    mejor_score = -1
    mejor_detector = ""

    for nombre, v in data.items():
        tp = v["true_positives"]
        prec = v["precision"]
        rec = v["recall"]
        f1 = v["f1_score"]
        iou = v["mean_iou"]
        t = v["avg_inference_time"]
        t_norm = t / max_time
        score = round(0.5 * (1 - t_norm) + 0.4 * f1 + 0.1 * iou, 3)

        if score > mejor_score:
            mejor_score = score
            mejor_detector = nombre

        filas.append((nombre, tp, prec, rec, f1, iou, t, score))

    filas.sort(key=lambda x: x[-1], reverse=True)

    for fila in filas:
        score_fnmt = r"\textbf{" + f"{fila[7]:.3f}" + "}" if fila[0] == mejor_detector else fila[7]
        print(f"    {real_name(fila[0]):20} & {fila[1]:4} & {fila[2]:.4f} & {fila[3]:.4f} & {fila[4]:.4f} & {fila[5]:.4f} & {fila[6]:.4f} & {score_fnmt} \\\\")

def real_name(str):
    return {
        "yolov5": "YOLOv5-face",
        "insightface": "InsightFace-lite",
        "dlib_cnn": "DLIB CNN",
        "yolov8": "YOLOv8-face",
        "mtcnn": "MTCNN",
        "retinaface": "RetinaFace",
        "dlib_frontal": "DLIB Frontal",
        "cv2": "OpenCV (Haar)"
    }[str]

procesar_resultados("test_detector_results_mapir.json")
print("\n\n")
procesar_resultados("test_detector_results_widerface.json")
