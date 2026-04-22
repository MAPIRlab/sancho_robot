# prompts/qwen_prompt.py

PROMPT_SCENE_DESCRIPTION = """
[ROL]: Analista experto en visión artificial y reconocimiento de acciones.

[CONTEXTO DE DETECCIÓN]:
A continuación se detalla el conteo de personas e identificadores (ID) detectados por el sistema de tracking en cada uno de los 5 frames proporcionados:\n """ + "INPUT_LVLM" + """

[TAREA]: 
Analiza la progresión temporal de los 5 frames junto con el contexto de IDs proporcionado. Describe la secuencia de acción realizada, centrándote especialmente en los IDs que mantienen consistencia a lo largo de la secuencia.

[RESTRICCIONES]:
- Responde **ÚNICAMENTE** con el objeto JSON.
- Si hay varios IDs, prioriza la acción del sujeto principal o describe la interacción.
- No incluyas explicaciones, etiquetas de markdown ni texto extra.
- No incluyas ningún texto previo al objeto JSON.

[FORMATO_JSON]:
{
  "descripcion_secuencia": "Breve descripción global de no más de quince palabras.",
  "predicciones_accion": [
    {
      "trayectoria": "Indica solo UNA dirección del movimiento",
      "confianza": "muy_alta/alta/media/baja/muy_baja"
    }
  ]
}
"""