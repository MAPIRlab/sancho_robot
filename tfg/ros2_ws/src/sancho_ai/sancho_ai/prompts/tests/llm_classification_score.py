import json
import os

# Diccionario de nombres amigables
def nombre_amigable(nombre):
    return {
        "gpt-3.5-turbo": "GPT 3.5 Turbo",
        "gpt-4": "GPT 4",
        "gpt-4o": "GPT 4o",
        "meta-llama/Llama-3.1-8B-Instruct": "LLaMA 3.1 8B",
        "meta-llama/Llama-3.3-70B-Instruct": "LLaMA 3.3 70B",
        "deepseek-ai/deepseek-llm-7b-chat": "DeepSeek 7B",
        "deepseek-ai/deepseek-llm-67b-chat": "DeepSeek 67B",
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B": "DeepSeek R1 LLaMA 70B",
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B": "DeepSeek R1 Qwen 32B",
        "Qwen/Qwen1.5-7B-Chat": "Qwen 1.5 7B",
        "Qwen/Qwen2.5-7B-Instruct": "Qwen 2.5 7B",
        "Qwen/Qwen2.5-14B-Instruct": "Qwen 2.5 14B",
        "Qwen/Qwen2.5-32B-Instruct": "Qwen 2.5 32B",
        "Qwen/Qwen2.5-72B-Instruct": "Qwen 2.5 72B",
        "01-ai/Yi-1.5-9B-Chat": "Yi 1.5 9B",
        "01-ai/Yi-1.5-34B-Chat": "Yi 1.5 34B",
        "gemini-1.5-flash-latest": "Gemini 1.5 Flash",
        "gemini-2.0-flash-lite": "Gemini 2.0 Lite",
        "gemini-2.5-flash": "Gemini 2.5 Flash",
        "google/gemma-3-27b-it": "Gemma 3 27B",
        "mistralai/Mistral-7B-Instruct-v0.1": "Mistral 7B",
        "tiiuae/Falcon3-10B-Instruct": "Falcon 3 10B",
        "microsoft/phi-2": "Phi-2"
    }.get(nombre, nombre)

def procesar_llm_classification(path_json):
    path = os.path.join(os.path.dirname(__file__), path_json)
    with open(path) as f:
        data = json.load(f)

    max_time = 0
    resultados = []

    # Calcular tiempo máximo
    for proveedor in data.values():
        for modelo in proveedor.values():
            t_total = modelo["total_time_sec"]
            n = modelo["total_tests"]
            t_avg = t_total / n
            max_time = max(max_time, t_avg)

    for proveedor, modelos in data.items():
        for nombre, v in modelos.items():
            T = v["total_tests"]
            TP = v["intent_and_args_correct"]
            VJ = v["valid_json"]
            t_avg = v["total_time_sec"] / T

            precision = TP / VJ if VJ else 0
            recall = TP / T if T else 0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0
            score = 0.4 * f1 + 0.1 * (VJ / T) + 0.5 * (1 - t_avg / max_time)

            resultados.append({
                "nombre": nombre_amigable(nombre),
                "TP": TP,
                "valid_json": VJ,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "t_avg": t_avg,
                "score": score
            })

    resultados.sort(key=lambda x: x["score"], reverse=True)
    mejor = resultados[0]["nombre"]

    # Imprimir tabla LaTeX
    for r in resultados:
        score_fmt = f"\\textbf{{{r['score']:.3f}}}" if r["nombre"] == mejor else f"{r['score']:.3f}"
        print(
            f"    {r['nombre']:30} & {r['TP']:2} & {r['valid_json']:2} & "
            f"{r['precision']:.4f} & {r['recall']:.4f} & {r['f1']:.4f} & "
            f"{r['t_avg']:.4f} & {score_fmt} \\\\"
        )

# Llamada al script
print("CLASIFICACIÓN DE INTENCIONES CON LLMs")
procesar_llm_classification("results_llm.json")
