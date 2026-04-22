PROMPT_ACTION_PREDICTION = """[ROL]: EXPERTO EN CLASIFICADOR DE ACCIONES HUMANAS.

        [TAREA]: Analiza los 3 análisis de video adjuntos y extrae una UNICA acción general que englobe el comportamiento. Responde únicamente en el formato JSON especificado, no respondas ni añadas ningún texto más.
        [DATOS_DE_ENTRADA]:\n   """ + "INPUT_LLM" + """


        [RESTRICCIONES]:
        1. RESPONDER EXCLUSIVAMENTE EN FORMATO JSON VALIDO, No se debe incluir ningún tipo de texto extra. Utiliza exclusivamente comillas dobles estándar ASCII para JSON.
        2. 'accion_final': DEBE tener entre 1 a 3 palabras como MAXIMO. DEBE derivarse directamente de las descripciones anteriores. EVITAR verbos genéricos como "HACER","PREPARAR","IR", "MOVER" y EVITAR sustantivos abstractos como "FLEXIBILIDAD", "MOVIMIENTO" entre otros.
        3. 'Justifiación_breve': Debes describir en máximo 15 palabras qué objetos o acciones te han llevado a clasificar la 'accion_final' utilizando de manera OBLIGATORIA el formato: "Objeto:"..., "Acciones:"....

        [FORMATO_DE_SALIDA_EN_JSON]:
        {
        "accion_final": "...",
        "confianza_prediccion": "muy_alta/alta/media/baja/muy_baja",
        "justificacion_breve": "..."
        }
        """