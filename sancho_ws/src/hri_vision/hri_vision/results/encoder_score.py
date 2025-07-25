import json
import os

def real_name(name):
    return {
        "facenet": "FaceNet",
        "vggface": "VGGFace",
        "sface": "SFace",
        "arcface": "ArcFace",
        "openface": "OpenFace",
        "dinov2": "DinoV2"
    }.get(name, name)

def procesar_encoders(path_json):
    path = os.path.join(os.path.dirname(__file__), path_json)
    with open(path) as f:
        data = json.load(f)
    
    modelos = {k: v for k, v in data.items() if not k.endswith("_")}

    max_time = max(v["avg_recognition_time"] for v in modelos.values())
    max_dim = max(v["embedding_size"] for v in modelos.values())
    max_q = max(v["name_questions"] + v["confirm_questions"] for v in modelos.values())

    filas = []
    mejor_score = -1
    mejor_encoder = ""

    for nombre, v in modelos.items():
        tp = v["true_positives"]
        prec = v["precision"]
        rec = v["recall"]
        f1 = v["f1_score"]
        dim = v["embedding_size"]
        t = v["avg_recognition_time"]
        q = v["name_questions"] + v["confirm_questions"]
        silh = v["silhouette_score"]
        ch = v["calinski_harabasz_score"]

        score = round(
            0.6 * prec +
            0.1 * (1 - t / max_time) +
            0.1 * (1 - dim / max_dim) +
            0.2 * (1 - q / max_q), 3
        )

        if score > mejor_score:
            mejor_score = score
            mejor_encoder = nombre

        filas.append((nombre, dim, tp, prec, rec, f1, t, q, silh, ch, score))

    filas.sort(key=lambda x: x[-1], reverse=True)

    for fila in filas:
        score_fmt = r"\textbf{" + f"{fila[10]:.3f}" + "}" if fila[0] == mejor_encoder else f"{fila[10]:.3f}"
        print(f"    {real_name(fila[0]):10} & {fila[1]:4} & {fila[2]:4} & {fila[3]:.4f} & {fila[4]:.4f} & {fila[5]:.4f} & {fila[6]:.4f} & {fila[7]:3} & {fila[8]:.4f} & {fila[9]:.2f} & {score_fmt} \\\\")

procesar_encoders("test_encoder_results.json")
