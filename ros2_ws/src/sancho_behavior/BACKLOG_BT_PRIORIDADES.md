# Backlog Ejecutable - Arquitectura de Control por Prioridades

Objetivo: convertir el árbol actual en una arquitectura robusta de 4 capas con frontera clara entre misiones (L3) e idle (L4), preempción correcta y política energética operativa.

## Revision Tecnica (2026-04-21)

Estado verificado en codigo:
- EPICA A: implementada y consistente con los criterios de BTA-001 y BTA-002.
- EPICA B: implementada y consistente con los criterios de BTA-010 y BTA-011.
- EPICA C: implementada y consistente con los criterios de BTA-020, BTA-021 y BTA-022.
- EPICA E: implementada y consistente con los criterios de BTA-040 y BTA-041.
- EPICA F: implementada y consistente con los criterios de BTA-050 y BTA-051.

Nota:
- El detalle fino de decisiones antiguas se mantiene en historial de commits/PRs.
- Este backlog prioriza desde ahora las epicas nuevas (H, I, J).

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

## 5) Resumen de estado (compacto)

Epicas implementadas y cerradas (detalle historico omitido para ahorrar mantenimiento):
- EPICA A (BTA-001, BTA-002): observabilidad y estado global BB.
- EPICA B (BTA-010, BTA-011): survival operativo y politica degraded.
- EPICA C (BTA-020, BTA-021, BTA-022): preempcion humana robusta con handshake real.
- EPICA E (BTA-040, BTA-041): idle funcional y modo ahorro.
- EPICA F (BTA-050, BTA-051): frontera L3/L4 y cooldown anti-oscilacion.

Backlog legado pendiente (bajo foco actual):
- EPICA D (BTA-030, BTA-031, BTA-032): framework multi-mision en L3.
- EPICA G (BTA-060): validacion/humo de escenarios de prioridad.

## 6) Validación mínima (solo cuando aplique)

Ejecutar desde ros2_ws:

1. source /opt/ros/humble/setup.bash
2. colcon build --symlink-install --packages-select sancho_interfaces sancho_behavior
3. source install/setup.bash
4. ros2 run sancho_behavior sancho_behavior_tree

Opcional humo integración:
- ros2 launch sancho_behavior sancho_interaction.launch.py

## 7) Handoff minimo entre agentes

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

## 8) Roadmap de Escalabilidad (Siguiente Fase)

Motivación:
- El árbol principal ya tiene múltiples capas y subflujos complejos.
- Se prevé crecimiento rápido de comportamientos complejos (ej. gaze-shifting, conversación, tracking social).
- Es necesario reducir acoplamiento, mejorar reusabilidad y definir contratos de interrupción/reanudación robustos.

Estado actual relevante (auditado):
- `Priorities` en L1-L4 ya usa `memory=False` (preempción correcta global).
- Subárboles de larga duración (`L3_Mission`, parte de L2) usan `memory=True` para reanudación.
- Existen artefactos vacíos en `trees/` (`importlib`, `os`, `py_trees`, `sys`) que deben limpiarse para evitar deuda técnica.
- Existe un `interaction_tree.py` no integrado en el root actual y con dependencias potencialmente desalineadas (`behaviors.tracking`, `SetFaceMode`, etc.).

## 9) Opciones de Diseño para Capacidades Persistentes

Opción A - Rama paralela in-tree (todo dentro del BT principal):
- Pros: visibilidad completa en un único árbol.
- Contras: más riesgo de colisión de actuadores (head/base/face), acoplamiento fuerte, debugging más complejo.

Opción B - Capability Manager externo (nodo ROS 2 dedicado):
- Pros: separación de responsabilidades, lifecycle independiente, reuso alto entre ramas.
- Contras: más infraestructura (APIs, contratos, observabilidad entre nodos).

Opción C - Híbrida (recomendada):
- Mantener en rama paralela solo capacidades persistentes de estado/sensado (read-mostly).
- Delegar capacidades de actuación continua a un Capability Manager con arbitraje explícito.
- Evita condiciones de carrera y mantiene al BT como orquestador, no como multiplexor de bajo nivel.

Recomendación:
- Adoptar Opción C en 2 fases: primero infraestructura y contratos (sin cambiar comportamiento), luego migrar capacidades complejas una a una.

## EPICA H - Modularidad BT y Patron Proxy-Subtree ✅ IMPLEMENTADA (2026-04-22)

BTA-070 - Higiene del paquete trees ✅ DONE
- Objetivo: eliminar artefactos y ambigüedad estructural en `trees/`.
- Archivos tocados:
  - [sancho_behavior/trees](sancho_behavior/trees) — se borraron `importlib`, `os`, `py_trees`, `sys`.
- Entregable:
  - Eliminados archivos vacíos/no funcionales.
  - `interaction_tree.py` documentado como integrado vía ProxySubtreeBehavior.
- Criterio Done: ✅ Verificado list_dir sin artefactos huérfanos.
- Dependencias: ninguna.
- Handoff: Limpieza exitosa de deuda técnica.

BTA-071 - Registry de factories de subárboles ✅ DONE
- Objetivo: estandarizar creación de subárboles complejos mediante factories.
- Archivos tocados:
  - [sancho_behavior/behaviors/factories.py](sancho_behavior/behaviors/factories.py) — creado nuevo registry.
- Entregable:
  - `behaviors/factories.py` con interfaz de factory y decorador de registro.
- Criterio Done: ✅ Factory interface `SubtreeFactory` definido e implementado.
- Dependencias: BTA-070.
- Handoff: Utilizar `@SubtreeRegistry.register("nombre")` para registrar nuevos subárboles.

BTA-072 - Infraestructura base ProxySubtree ✅ DONE
- Objetivo: encapsular subárboles complejos como “nodos hoja” hacia el padre.
- Archivos tocados:
  - [sancho_behavior/behaviors/proxy_subtree.py](sancho_behavior/behaviors/proxy_subtree.py) — creado ProxySubtreeBehavior.
- Entregable:
  - `ProxySubtreeBehavior` implementado, usa el factory internamente y transfiere el estado del tick de forma transparente.
- Criterio Done: ✅ `ProxySubtreeBehavior` encapsula subárboles correctamente sin exponerlos al render principal.
- Dependencias: BTA-071.
- Handoff: Permite modularidad fuerte y oculta detalles del subárbol a su padre.

BTA-073 - Migrar ReactToSound a proxy-subtree ✅ DONE
- Objetivo: convertir `ReactToSound` en primer caso real del patrón.
- Archivos tocados:
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py) — usando proxy.
  - [sancho_behavior/trees/react_to_sound_tree.py](sancho_behavior/trees/react_to_sound_tree.py) — usando registry.
- Entregable:
  - L2 consume un nodo proxy en lugar de importar la factory directamente.
- Criterio Done: ✅ Integrado correctamente en preemption_tree.
- Dependencias: BTA-072.

BTA-074 - Migrar flujo de interacción compleja a proxy-subtree ✅ DONE
- Objetivo: encapsular conversación/engagement/tracking social en un proxy reusable.
- Archivos tocados:
  - [sancho_behavior/trees/interaction_tree.py](sancho_behavior/trees/interaction_tree.py) — añadido registry y mocks explícitos.
- Entregable:
  - Subárbol registrado y funcional para integración BT con mocks explícitos.
- Criterio Done: ✅ interaction_tree.py utiliza registry. Los behaviors faltantes fueron mockeados según solicitud.
- Nota de alcance:
  - Pendiente de producción: sustituir mocks por behaviors reales de conversación/tracking.
- Dependencias: BTA-072.

BTA-075 - Contrato de blackboard por namespaces ✅ DONE
- Objetivo: evitar colisiones de claves BB y facilitar mantenimiento.
- Archivos tocados:
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py) — añadido doc block con convenciones.
  - [README de paquete](README.md) — sección añadida para namespaces.
- Entregable:
  - Convención documentada: `layer/<name>/...`, `mission/...`, `capability/...`, `config/...`.
- Criterio Done: ✅ README y main_tree actualizados con los estándares.
- Dependencias: BTA-071.

## EPICA I - Contrato de Interrupcion y Reanudacion ✅ IMPLEMENTADA (2026-04-22)

BTA-080 - Auditoría de memory policies ✅ DONE
- Objetivo: verificar y documentar `memory=False` en selectores de prioridad y `memory=True` en misiones largas.
- Archivos:
  - [docs/memory_policies_audit.md](docs/memory_policies_audit.md) — matriz capa/composite/memory creada.
- Entregable:
  - Matriz capa/composite/memory con justificación.
- Criterio Done: ✅ Documentado y verificado. Sin inconsistencias.
- Dependencias: ninguna.

BTA-081 - API de preempción estándar para subárboles largos ✅ DONE
- Objetivo: definir protocolo uniforme de interrupción limpia y continuación.
- Archivos:
  - [sancho_behavior/behaviors/preemption_contract.py](sancho_behavior/behaviors/preemption_contract.py) — `WithPreemptionContract` decorator creado.
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py) — L3 wrapped.
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py) — L2 wrapped.
- Entregable:
  - Contrato común (`PREEMPTED`, `RESUMABLE`, `NON_RESUMABLE`) implementado.
- Criterio Done: ✅ L3_Mission y L2_HumanPreemption soportan preempción/reanudación.
- Dependencias: BTA-072, BTA-080.

BTA-082 - Pruebas de regresión de preempción y resume ✅ DONE
- Objetivo: evitar regresiones al crecer el árbol.
- Archivos:
  - [scripts/test_preemption.py](scripts/test_preemption.py) — script de simulación.
  - [docs/tests/preemption_tests.md](docs/tests/preemption_tests.md) — evidencia de logs.
- Entregable:
  - Escenarios reproducibles con evidencia:
    1) L3 RUNNING interrumpido por L2 ✅,
    2) retorno y reanudación controlada ✅,
    3) L1 crítica forzando abort seguro ✅.
- Criterio Done: ✅ Evidencia de logs por escenario verificada.
- Dependencias: BTA-081.

## EPICA J - Capacidades Persistentes y Rama Paralela ✅ IMPLEMENTADA (2026-04-22)

BTA-090 - ADR de capacidades persistentes ✅ DONE
- Resultado: adoptada opción híbrida (rama runtime no intrusiva + handshake explícito con attention manager).
- Archivos tocados:
  - [README de paquete](README.md)
  - [docs/adr/ADR-0001-capability-runtime-hybrid.md](docs/adr/ADR-0001-capability-runtime-hybrid.md)

BTA-091 - Rama parallel CapabilitiesRuntime ✅ DONE
- Resultado: nueva rama persistente en root para estado de capacidades.
- Archivos tocados:
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py)
  - [sancho_behavior/trees/capabilities_tree.py](sancho_behavior/trees/capabilities_tree.py)
- Criterio Done: ✅ runtime paralelo activo sin comandos directos a actuadores.

BTA-092 - Arbitraje de recursos físicos ✅ DONE
- Resultado: ownership determinista por prioridad para recursos `head/base/face`.
- Archivos tocados:
  - [sancho_behavior/behaviors/capabilities_runtime.py](sancho_behavior/behaviors/capabilities_runtime.py)
  - [sancho_behavior/trees/main_tree.py](sancho_behavior/trees/main_tree.py)
- Criterio Done: ✅ una sola propiedad activa por recurso en blackboard.

BTA-093 - Tracking reusable con TTL ✅ DONE
- Resultado: tracking desacoplado del cierre instantáneo de interacción, con ventana TTL configurable y observable.
- Archivos tocados:
  - [sancho_behavior/interaction/attention_manager_node.py](sancho_behavior/interaction/attention_manager_node.py)
  - [sancho_behavior/interaction/interaction_manager_node.py](sancho_behavior/interaction/interaction_manager_node.py)
- Criterio Done: ✅ endpoint y publisher de `active_until` operativos.

BTA-094 - Handshake de capacidades desde BT ✅ DONE
- Resultado: contrato común de behaviors para `enable/disable/set_mode` usado por L2 y L3.
- Archivos tocados:
  - [sancho_behavior/behaviors/capability_control.py](sancho_behavior/behaviors/capability_control.py)
  - [sancho_behavior/trees/preemption_tree.py](sancho_behavior/trees/preemption_tree.py)
  - [sancho_behavior/trees/mission_tree.py](sancho_behavior/trees/mission_tree.py)
- Criterio Done: ✅ L2 y L3 invocan la misma API de capability tracking.

## 10) Plan de ejecución recomendado (nueva fase)

Fase 1 (estructura segura):
- BTA-070 -> BTA-071 -> BTA-072

Fase 2 (migración incremental a proxy):
- BTA-073
- BTA-074

Fase 3 (interrupción/reanudación robusta):
- BTA-080 -> BTA-081 -> BTA-082

Fase 4 (capacidades persistentes):
- BTA-090 -> BTA-091 -> BTA-092 -> BTA-093 -> BTA-094 ✅

## 11) Riesgos y mitigaciones

Riesgo: carrera de comandos al actuador de cabeza entre ramas.
- Mitigación: BTA-092 obligatorio antes de habilitar capacidades persistentes de actuación.

Riesgo: proliferación de claves BB globales no trazables.
- Mitigación: BTA-075 (namespaces) antes de migrar más subárboles.

Riesgo: proxy-subtree sin contrato de preempción uniforme.
- Mitigación: BTA-081 + pruebas BTA-082.
