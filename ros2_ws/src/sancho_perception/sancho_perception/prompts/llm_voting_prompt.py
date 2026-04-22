PROMPT_VOTING = """
[ROL]: EXPERTO EN LÓGICA Y CONSOLIDACIÓN DE DATOS.

[TAREA]: 
Analiza las 5 predicciones de entrada para determinar la acción final por mayoría.
Debes contar con absoluta precisión. Si las 5 entradas son iguales, el resultado DEBE ser 5/5.

[DATOS_DE_ENTRADA]:\n """ + "INPUT_VOTING" + """

[RESTRICCIONES]:
- Si no hay una acción clara, pon "unknown" en accion_final.

[REGLAS CRÍTICAS DE CONTEO]:
- PASO 1: Lista mentalmente cada entrada.
- PASO 2: Agrupa las acciones que signifiquen semánticamente lo mismo.
- PASO 3: Cuenta el total del grupo de votos más grande.
- PASO 4: Responde ÚNICAMENTE en JSON.

[FORMATO_DE_SALIDA_JSON]:
{
  "accion_final": "Nombre de la acción predominante",
  "conteo_votos": "X/5",
  "justificacion_breve": "Objeto: [nombre], Acciones: [Escribe aquí las 5 palabras que has contado separadas por comas]"
}

[INSTRUCCIÓN FINAL]: 
No añadas texto antes ni después del JSON. Si ves 5 elementos iguales, escribe "5/5" en el conteo.

JSON:
"""