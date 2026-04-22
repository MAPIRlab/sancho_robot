# Auditoría de Memory Policies en Behavior Tree (BTA-080)

En Behavior Trees (`py_trees`), la política `memory` determina si un nodo compuesto (Sequence, Selector) recuerda su estado anterior si es interrumpido o si empieza desde el primer hijo en cada *tick*.

Esta auditoría documenta y justifica las políticas adoptadas en el árbol principal (`main_tree.py`) y sus ramas.

## 1. Top-Level Orchestration
| Nodo | Tipo | Memory | Justificación |
|---|---|---|---|
| `Priorities` | Selector | **False** | Es el árbitro principal. Debe re-evaluar de izquierda a derecha (L1 $\rightarrow$ L2 $\rightarrow$ L3 $\rightarrow$ L4) en cada tick para garantizar preempción reactiva e inmediata (ej. si salta `battery_critical`, toma control L1, interrumpiendo lo que haya a su derecha). |
| `L3_AdmissionAndExecution` | Sequence | **False** | Agrupa la admisión (`HasWaypoint?`) y la ejecución (`L3_Mission`). Si pierde el tick (preempción), al volver a ganar control debe re-evaluar `HasWaypoint?` para no continuar a ciegas. |

## 2. Nodos Raíz de Capas (Layers)
| Capa | Nodo Raíz | Tipo | Memory | Justificación |
|---|---|---|---|---|
| **L1** | `L1_Survival` | Sequence | **True** | Una vez se dispara una acción de supervivencia (ej. ir al Docking), no debe abortar a la mitad por oscilaciones en sensores. Debe terminar la secuencia. |
| **L2** | `L2_HumanPreemption`| Sequence | **True** | Las interacciones sociales (escuchar, responder) requieren mantener estado a lo largo de varios ticks. Si L1 toma el control y luego devuelve, L2 continuará la conversación. |
| **L3** | `L3_Mission` | Sequence | **True** | Las misiones son de larga duración. Si son pausadas por L2 (humano interrumpe), al volver deben retomar la navegación (resume) y no volver a empezar la misión desde cero. |
| **L4** | `L4_Idle` | Sequence | **True** | El comportamiento de vagar o ahorrar energía se mantiene hasta ser abortado. |

## 3. Sub-Nodos de Flujo Interno
| Nodo Interno | Tipo | Memory | Justificación |
|---|---|---|---|
| `PreemptionFlow` (L2) | Selector | **False** | Elige entre éxito (resume) y fallo de interacción. Si la interacción falla a la mitad, se limpia estado. |
| `PreemptionFailureCleanup` (L2)| Sequence | **False** | Nodo de limpieza rápido, se ejecuta en un solo tick. |
| `IdlePolicy` (L4) | Selector | **False** | Decide entre ahorrar energía o patrullar. Debe re-evaluarse dinámicamente si la batería cambia (L4 es la rama final, así que se tickea siempre que no haya L1/L2/L3). |

## Conclusión
Las políticas actuales son **consistentes y correctas**:
- `memory=False` se usa exclusivamente en Selectors de prioridad y secuencias reactivas de admisión.
- `memory=True` se usa exclusivamente para proteger flujos de trabajo (workflows) de larga duración de ser abortados erróneamente en re-ticks.
