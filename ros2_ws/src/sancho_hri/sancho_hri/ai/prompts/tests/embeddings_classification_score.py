import json
import os

# Mapeo de nombres amigables
def nombre_amigable(nombre):
    return {
        "text-embedding-3-small": "OpenAI 3 Small",
        "text-embedding-3-large": "OpenAI 3 Large",
        "text-embedding-ada-002": "OpenAI Ada-002",
        "text-embedding-babbage-001": "OpenAI Babbage",
        "Alibaba-NLP/gte-Qwen2-7B-instruct": "Qwen2 GTE 7B",
        "deepseek-ai/deepseek-coder-6.7b-instruct": "DeepSeek Coder 6.7B",
        "sentence-transformers/all-MiniLM-L6-v2": "MiniLM-L6-v2",
        "intfloat/e5-large-v2": "E5 Large",
        "BAAI/bge-m3": "BGE-M3",
        "BAAI/bge-base-en-v1.5": "BGE Base v1.5"
    }.get(nombre, nombre)

# Mapeo de dimensiones conocidas
dimensiones = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "text-embedding-babbage-001": 2048,
    "Alibaba-NLP/gte-Qwen2-7B-instruct": 1024,
    "deepseek-ai/deepseek-coder-6.7b-instruct": 4096,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "intfloat/e5-large-v2": 1024,
    "BAAI/bge-m3": 1024,
    "BAAI/bge-base-en-v1.5": 768
}

def procesar_embeddings(path_json):
    path = os.path.join(os.path.dirname(__file__), path_json)
    with open(path) as f:
        data = json.load(f)

    max_time = 0
    max_dim = max(dimensiones.values())
    resultados = []

    # Cálculo del tiempo máximo
    for proveedor in data.values():
        for nombre, v in proveedor.items():
            t_avg = v["total_time_sec"] / v["total_tests"]
            max_time = max(max_time, t_avg)

    for proveedor, modelos in data.items():
        for nombre, v in modelos.items():
            T = v["total_tests"]
            TP = v["intent_correct"]
            FP = T - TP
            precision = TP / (TP + FP) if (TP + FP) else 0
            recall = TP / T if T else 0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0
            t_avg = v["total_time_sec"] / T
            D = dimensiones[nombre]
            score = (
                0.65 * f1 +
                0.25 * (1 - t_avg / max_time) +
                0.1 * (1 - D / max_dim)
            )

            resultados.append({
                "nombre": nombre_amigable(nombre),
                "TP": TP,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "t_avg": t_avg,
                "dim": D,
                "score": score
            })

    resultados.sort(key=lambda x: x["score"], reverse=True)
    mejor = resultados[0]["nombre"]

    # Imprimir tabla en formato LaTeX
    for r in resultados:
        score_fmt = f"\\textbf{{{r['score']:.3f}}}" if r["nombre"] == mejor else f"{r['score']:.3f}"
        print(
            f"    {r['nombre']:28} & {r['TP']:2} & {r['precision']:.4f} & {r['recall']:.4f} & "
            f"{r['f1']:.4f} & {r['t_avg']:.4f} & {r['dim']:4} & {score_fmt} \\\\"
        )

# Llamada
print("CLASIFICACIÓN DE INTENCIONES CON EMBEDDINGS")
procesar_embeddings("results_embeddings.json")
