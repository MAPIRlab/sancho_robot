# ADR-0001: Capability Runtime Hibrido

Fecha: 2026-04-22
Estado: Aprobado

## Contexto

El BT principal requiere capacidades persistentes reutilizables (tracking, atencion,
modos de percepcion) sin comprometer preempcion por prioridades ni introducir
carreras entre actuadores.

Opciones evaluadas:

- A: todo in-tree en una rama paralela con actuacion directa.
- B: capability manager completamente externo al BT.
- C: hibrido (runtime in-tree no intrusivo + handshake explicito a nodos externos).

## Decision

Se adopta opcion C (hibrida):

- El BT mantiene una rama paralela persistente para estado de capacidades,
  TTL y arbitraje de ownership de recursos.
- La actuacion concreta (activar/desactivar tracking, modos) se realiza por
  APIs explicitas del attention manager.
- L2 y L3 usan el mismo contrato de capacidad (`enable/disable/set_mode`).

## Consecuencias

Positivas:

- Menor acoplamiento entre capas BT y nodos de atencion.
- Capacidad reutilizable entre L2 y L3.
- Prevencion temprana de conflictos por ownership de recursos.

Negativas:

- Mas puntos de integracion (servicios/temas).
- Requiere observabilidad de tiempo (TTL) y pruebas de integracion.

## Implementacion asociada

- `sancho_behavior/trees/capabilities_tree.py`
- `sancho_behavior/behaviors/capabilities_runtime.py`
- `sancho_behavior/behaviors/capability_control.py`
- `sancho_behavior/interaction/attention_manager_node.py`
- `sancho_behavior/interaction/interaction_manager_node.py`
