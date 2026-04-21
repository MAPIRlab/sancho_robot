# Backlog Ejecutable - Arquitectura de Control por Prioridades

Objetivo: convertir el árbol actual en una arquitectura robusta de 4 capas con frontera clara entre misiones (L3) e idle (L4), preempción correcta y política energética operativa.

## Revision Tecnica (2026-04-21)

Estado verificado en codigo:
- EPICA A: implementada y consistente con los criterios de BTA-001 y BTA-002.
- EPICA B: implementada y consistente con los criterios de BTA-010 y BTA-011.
- EPICA C: implementada y consistente con los criterios de BTA-020, BTA-021 y BTA-022.
- EPICA E: implementada y consistente con los criterios de BTA-040 y BTA-041.
- EPICA F: implementada y consistente con los criterios de BTA-050 y BTA-051.

Decision de diseno validada:
- La guarda `IsNotBatteryDegraded?` dentro de L3 fue una decision intencional de BTA-011 para control de admision de nuevas misiones.
- Con `Sequence(memory=True)` en L3, una mision ya en RUNNING no se aborta por esta guarda; la guarda se aplica al iniciar/reingresar, no en cada tick de un hijo ya en ejecucion.

Nota de arquitectura (aislamiento):
- Esta implementacion introduce acoplamiento politico (energia) dentro de L3, pero no acoplamiento funcional fuerte.
- Si se desea aislamiento estricto por capas, mover la admision energetica a una capa de arbitraje en `main_tree.py` (wrapper de L3) y mantener `mission_tree.py` agnostico de bateria.
- Ese ajuste queda alineado con EPICA F (BTA-050).

## 1) Alcance

Incluido:
- sancho_behavior (árbol principal, subárboles, behaviours de navegación/interacción/lifecycle)
- Integración con sancho_interfaces ya existentes (sin añadir interfaces nuevas en esta primera fase)

Excluido por ahora:
- Rediseño profundo de sancho_hri, sancho_audio, sancho_navigation
- Cambios no necesarios en paquetes third_party

## 2) Punto de partida (estado actual)

Referencias de lectura obligatoria antes de codificar:
- [README de paquete](README.md)
- [Árbol principal](sancho_behavior/trees/main_tree.py)
- [L1 Survival](sancho_behavior/trees/survival_tree.py)
- [L2 Preemption](sancho_behavior/trees/preemption_tree.py)
- [L3 Mission](sancho_behavior/trees/mission_tree.py)
- [L4 Idle](sancho_behavior/trees/idle_tree.py)
- [Battery monitor con histéresis](sancho_behavior/behaviors/battery_monitor.py)
- [Behaviors de navegación](sancho_behavior/behaviors/navigation.py)
- [Behaviors de interacción](sancho_behavior/behaviors/interaction.py)

## 3) Contrato funcional objetivo

L1 Survival:
- Prioridad máxima incondicional.
- Usa histéresis de batería para proteger de oscilaciones.
- Si battery_critical: aborta misión activa y fuerza retorno a docking.
- Si battery_degraded: bloquea admisión de nuevas misiones L3 y limita L4 a modo ahorro.

L2 Human Preemption:
- Solo se activa con evento de interrupción válido (ejemplo: hotword_event).
- Pausa temporalmente navegación/misión, orienta y gestiona interacción corta.
- Al terminar, reanuda o devuelve control sin dejar Nav2 pausado.

L3 High-Level Missions:
- Misiones explícitas con mission_id, mission_type, goal y criterio de éxito/fallo.
- Deben ser cancelables y reanudables ante preempción de L1/L2.

L4 Idle:
- Comportamientos oportunistas y seguros (roaming ligero, escaneo pasivo, housekeeping).
- Siempre interrumpible por L1/L2/L3.

Frontera L3/L4:
- L3 requiere objetivo formal y seguimiento.
- L4 no requiere objetivo formal ni trazabilidad de misión.

## 4) Estructura de trabajo para agentes

Reglas de coordinación:
- Cada agente toma 1 tarea con ID.
- No mezclar tareas de distintas épicas en una misma PR.
- Respetar dependencias entre tareas.
- Mantener cambios acotados al archivo/ruta indicada.

Plantilla mínima de branch por tarea:
- feat/bt-BTA-XXX-descripcion-corta

Plantilla mínima de commit:
- BTA-XXX: descripcion corta del cambio

## 5) Backlog por épicas y tareas

## EPICA A - Semántica base y observabilidad ✅ IMPLEMENTADA (2026-04-21)

BTA-001 - Definir estado operativo en blackboard ✅ DONE
- Objetivo: introducir claves de estado global para arbitraje de capas.
- Archivos tocados:
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py) — cliente ArbitrationState + cliente Observability añadidos en main()
- Entregable:
  - Claves inicializadas: mission/active=False, mission/type="", mission/id="", preemption/active=False.
  - Claves de observabilidad: active_layer="none", active_reason="initialising".
- Criterio Done: ✅ Árbol arranca sin errores y muestra valores iniciales consistentes.
- Dependencias: ninguna.
- Handoff: Sin riesgos. Estas claves son prerequisito de BTA-011 y BTA-030.

BTA-002 - Publicar motivo de capa activa ✅ DONE
- Objetivo: mejorar trazabilidad de por qué el selector está en L1, L2, L3 o L4.
- Archivos tocados:
  - [sancho_behavior/behaviors/layer_reporter.py](sancho_behavior/behaviors/layer_reporter.py) — NUEVO. LayerReporter behaviour (SUCCESS siempre, log sólo en transición).
  - [sancho_behavior/trees/survival_tree.py](sancho_behavior/trees/survival_tree.py) — LayerReporter[L1] como primer hijo.
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py) — LayerReporter[L2] como primer hijo.
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py) — LayerReporter[L3] como primer hijo.
  - [sancho_behavior/trees/idle_tree.py](sancho_behavior/trees/idle_tree.py) — LayerReporter[L4] como primer hijo.
- Criterio Done: ✅ Logs verificables en transición entre capas. Tree render confirmado OK.
- Dependencias: BTA-001.
- Handoff: Sin riesgos. LayerReporter es zero-cost (siempre SUCCESS, sin bloqueo).

## EPICA B - Survival completo (L1) ✅ IMPLEMENTADA (2026-04-21)

BTA-010 - Reemplazar AutoDock stub por acción real ✅ DONE
- Objetivo: dejar de usar Success stub en Survival.
- Archivos tocados:
  - [sancho_behavior/trees/survival_tree.py](sancho_behavior/trees/survival_tree.py) — Success("AutoDock") reemplazado por Timeout(120s) > NavigateToDock.
  - [sancho_behavior/behaviors/navigation.py](sancho_behavior/behaviors/navigation.py) — clase NavigateToDock añadida (FromBlackboard, lee config/dock_pose).
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py) — config/dock_pose inicializado en GlobalConfig (default: origen del mapa, w=1).
- Criterio Done: ✅ survival_tree children: [LayerReporter[L1], IsBatteryCritical?, DockTimeout]. Tree render OK.
- Dependencias: ninguna.
- Handoff:
  - dock_pose default es el origen del mapa. Override en runtime escribiendo config/dock_pose en el blackboard desde un nodo de configuración o parámetros.
  - El timeout de 120s es configurable cambiando el parámetro ``duration`` en el decorador Timeout de survival_tree.
  - Sin riesgos de regresión: NavigateToDock devuelve FAILURE si config/dock_pose no existe en blackboard (log de error).

BTA-011 - Política degraded para admisión de misiones ✅ DONE
- Objetivo: usar battery_degraded en el árbol de prioridad.
- Archivos tocados:
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py) — guarda IsNotBatteryDegraded? añadida como segundo hijo (tras LayerReporter[L3]).
  - [sancho_behavior/trees/idle_tree.py](sancho_behavior/trees/idle_tree.py) — IdlePolicy Selector añadido para bifurcar entre modo degradado y modo normal.
- Criterio Done: ✅ mission children incluye IsNotBatteryDegraded? y L4 cambia de política según `battery_degraded`.
- Dependencias: BTA-001.
- Handoff:
  - La guarda en L3 **es esperada** por alcance de BTA-011 (control de admision de nuevas misiones).
  - No corta misiones ya en curso mientras el hijo activo de la Sequence sigue RUNNING (`memory=True`).
  - Si se busca aislamiento estricto, planificar refactor en BTA-050 para mover la guarda al arbitraje de `main_tree.py`.
  - Transiciones a validar con hardware: normal → degraded (guarda L3 falla, L4 entra en DegradedIdle) → critical (L1 toma control) → recovery (flags se limpian en BatteryMonitor).
  - BTA-041 y BTA-040 ya sustituyen los stubs de idle por comportamientos reales.


## EPICA C - Human Preemption robusto (L2) ✅ IMPLEMENTADA (2026-04-21)

BTA-020 - Corregir orden de activación de preemption ✅ DONE
- Objetivo: evaluar hotword antes de pausar navegación.
- Archivos tocados:
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py) — gate `HotwordBeforePause?` añadido antes de `PauseNavigation`.
  - [sancho_behavior/trees/react_to_sound_tree.py](sancho_behavior/trees/react_to_sound_tree.py) — eliminada compuerta duplicada de hotword; el subtree queda puro de reacción.
- Entregable:
  - Sequence reestructurada con compuerta inicial por evento.
- Criterio Done: ✅
  - Sin hotword, L2 devuelve FAILURE antes de ejecutar `PauseNavigation`.
- Dependencias: ninguna.

BTA-021 - Cierre de ciclo con ResumeNavigation ✅ DONE
- Objetivo: no dejar navegación en estado pausado tras preempción.
- Archivos tocados:
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py) — `ResumeNavigation` en ruta de éxito y ruta de cleanup por fallo.
  - [sancho_behavior/behaviors/navigation.py](sancho_behavior/behaviors/navigation.py) — reutilización directa de `ResumeNavigation` existente.
- Entregable:
  - Reanudación explícita tras reacción/handshake y también en fallo post-pausa.
- Criterio Done: ✅
  - Tras L2 SUCCESS la navegación queda reanudada.
  - Si falla el flujo después de pausar, se ejecuta cleanup con reanudación antes de propagar FAILURE.
- Dependencias: BTA-020.

BTA-022 - Integrar trigger real de atención ✅ DONE
- Objetivo: eliminar TriggerAttentionManager stub.
- Archivos tocados:
  - [sancho_behavior/behaviors/preemption_checks.py](sancho_behavior/behaviors/preemption_checks.py) — NUEVO `EnsureAttentionManagerReady`.
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py) — reemplazo del stub por handshake real a `/attention_manager/interaction_finished` con timeout.
  - [launch/sancho_interaction.launch.py](launch/sancho_interaction.launch.py) — argumento `launch_attention_stack` para control explícito del stack de atención requerido por L2.
- Entregable:
  - Handshake real con endpoint de attention manager (sin stubs).
- Criterio Done: ✅
  - L2 ejecuta flujo completo sin `TriggerAttentionManager (Stub)`.
  - Handshake tiene timeout acotado (`timeout_sec=0.3`).
- Dependencias: BTA-020.

## EPICA D - Framework de misiones L3

BTA-030 - Introducir Mission Dispatcher
- Objetivo: permitir múltiples misiones de alto nivel sin acoplar L3 a una sola.
- Archivos:
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py)
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py)
- Entregable:
  - Selector o router interno de L3 por mission/type.
- Criterio Done:
  - Conviven al menos 2 submisiones con interfaz común.
- Dependencias: BTA-001.

BTA-031 - Refactor misión actual como mission_social_approach
- Objetivo: encapsular el flujo actual waypoint->interacción como submisión reutilizable.
- Archivos:
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py)
  - [sancho_behavior/behaviors/interaction.py](sancho_behavior/behaviors/interaction.py)
- Entregable:
  - Nodo/subárbol con entrada/salida estandarizada de misión.
- Criterio Done:
  - No cambia comportamiento funcional existente.
- Dependencias: BTA-030.

BTA-032 - Añadir misión placeholder real para remap o group-search
- Objetivo: crear segunda misión ejecutable (mínima) en L3.
- Archivos:
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py)
- Entregable:
  - Submisión con contrato formal (inicio, running, fin, error).
- Criterio Done:
  - Dispatcher selecciona correctamente según mission/type.
- Dependencias: BTA-030.

## EPICA E - Idle funcional (L4) ✅ IMPLEMENTADA (2026-04-21)

BTA-040 - Reemplazar RandomExplore stub ✅ DONE
- Objetivo: implementar comportamiento idle real con budget temporal.
- Archivos tocados:
  - [sancho_behavior/behaviors/idle_behaviors.py](sancho_behavior/behaviors/idle_behaviors.py) — NUEVO `IdleHeadSweep` con barrido periódico de cabeza en `/head_goal`.
  - [sancho_behavior/trees/idle_tree.py](sancho_behavior/trees/idle_tree.py) — reemplazo de `RandomExplore (Stub)` por `IdleHeadSweep`.
- Entregable:
  - Patrón de escaneo activo no bloqueante y preemptible.
- Criterio Done: ✅
  - L4 retorna RUNNING estable.
  - El comportamiento es cancelable por diseño al ser tick-driven y sin bloqueos.
- Dependencias: ninguna.

BTA-041 - Modo ahorro en idle bajo batería degradada ✅ DONE
- Objetivo: reducir agresividad del idle cuando battery_degraded=true.
- Archivos tocados:
  - [sancho_behavior/behaviors/idle_behaviors.py](sancho_behavior/behaviors/idle_behaviors.py) — NUEVO `EnergySavingStandby`.
  - [sancho_behavior/trees/idle_tree.py](sancho_behavior/trees/idle_tree.py) — rama `DegradedIdle` actualizada para usar `EnergySavingStandby`.
- Entregable:
  - Estrategia de ahorro con menor frecuencia de movimiento y postura de reposo.
- Criterio Done: ✅
  - Cambio observable de política de L4 con `battery_degraded`.
- Dependencias: BTA-040, BTA-011.

## EPICA F - Frontera L3-L4 explícita ✅ IMPLEMENTADA (2026-04-21)

BTA-050 - Contrato de admisión de misión ✅ DONE
- Objetivo: formalizar cuándo algo es L3 y cuándo debe vivir en L4.
- Archivos tocados:
  - [sancho_behavior/behaviors/mission_arbitration.py](sancho_behavior/behaviors/mission_arbitration.py) — NUEVO `MissionAdmissionGate`.
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py) — wrapper `L3_AdmissionAndExecution` con `MissionAdmissionGate` + misión.
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py) — eliminado acoplamiento de política energética; subtree centrado en ejecución.
  - [README de paquete](README.md) — sección "L3/L4 Admission Contract".
- Entregable:
  - Reglas explícitas de admisión en arbitraje (objetivo formal + batería + cooldown).
- Criterio Done: ✅
  - Sin objetivo formal, L3 no entra.
  - Con batería degradada, no se admiten nuevas entradas a L3.
- Dependencias: BTA-001, BTA-030, BTA-040.

BTA-051 - Enfriamiento anti-oscilación L3<->L4 ✅ DONE
- Objetivo: evitar ping-pong entre misión e idle.
- Archivos tocados:
  - [sancho_behavior/behaviors/mission_arbitration.py](sancho_behavior/behaviors/mission_arbitration.py) — NUEVO `MissionStatusTracker` (latch temporal).
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py) — claves `mission/cooldown_sec`, `mission/cooldown_until`, `mission/last_outcome`.
- Entregable:
  - Cooldown configurable tras salida de L3, aplicado en admisión.
- Criterio Done: ✅
  - Tras fin/fallo de misión, L3 queda bloqueada hasta expirar cooldown.
- Dependencias: BTA-050.

## EPICA G - Validación y humo

BTA-060 - Escenarios de prueba de prioridad
- Objetivo: validar preempción real entre capas.
- Archivos:
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py)
  - [README de paquete](README.md)
- Entregable:
  - Procedimiento reproducible para 4 escenarios:
    1) Hotword durante navegación
    2) batería_critical durante L3
    3) batería_degraded bloqueando nuevas misiones
    4) retorno estable a idle
- Criterio Done:
  - Evidencia de ejecución (logs) para cada escenario.
- Dependencias: BTA-010, BTA-021, BTA-041, BTA-051.

## 6) Plan de paralelización recomendado

Línea 1 (energía y seguridad):
- BTA-010 -> BTA-011

Línea 2 (preemption):
- BTA-020 -> BTA-021 -> BTA-022

Línea 3 (misiones):
- BTA-030 -> BTA-031 y BTA-032 en paralelo

Línea 4 (idle y frontera):
- BTA-040 -> BTA-041
- BTA-050 -> BTA-051

Cierre:
- BTA-060

## 7) Definition of Ready por tarea

Antes de empezar una tarea:
- Dependencias de tareas previas completadas.
- Confirmación de archivo objetivo y alcance acotado.
- Criterios de aceptación entendidos.

## 8) Definition of Done por PR

Para considerar una PR cerrada:
- Compila el workspace al menos para interfaces y behavior.
- Se puede ejecutar el árbol principal sin errores de setup.
- No quedan stubs en la funcionalidad objetivo de la tarea.
- README o comentarios mínimos actualizados cuando aplique.
- Incluye evidencia de comportamiento (logs de transición de capa).

## 9) Comandos de validación mínimos

Ejecutar desde ros2_ws:

1. source /opt/ros/humble/setup.bash
2. colcon build --symlink-install --packages-select sancho_interfaces sancho_behavior
3. source install/setup.bash
4. ros2 run sancho_behavior sancho_behavior_tree

Opcional humo integración:
- ros2 launch sancho_behavior sancho_interaction.launch.py

## 10) Plantilla de handoff entre agentes

Resumen:
- Tarea ID:
- Objetivo cumplido:
- Archivos tocados:
- Riesgos detectados:
- Qué falta:
- Cómo validar rápido:

Bloqueadores:
- Servicio o acción no disponible:
- Dependencia externa pendiente:
- Decisión de diseño pendiente:
