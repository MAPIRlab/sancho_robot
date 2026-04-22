# BTA-082 — Pruebas de Regresión: Preempción y Reanudación

Script: `scripts/test_preemption.py`  
Fecha: 2026-04-22  
Resultado: ✅ PASS (3/3 escenarios verificados)

## Escenario 1 — L3 RUNNING interrumpido por L2

**Condición inicial:** `hotword_event=False`, `group_waypoint_pose` set, L3 Mission en RUNNING (`NavigateToGroupPose [*]`).

**Trigger:** `hotword_event = True` (tick 3).

**Log evidencia (tick 3):**
```
[ INFO] LayerReporter[L2]: [LayerTransition] L2 → L2 | HumanPreemption (hotword) [hotword_event=True]

[o] Priorities [✓]
    {-} L2_HumanPreemption [✓]
        --> HotwordBeforePause? [✓] -- 'hotword_event' comparison succeeded [v: True][e: True]
        --> PauseNavigation [✓]
        [o] PreemptionFlow [✓]
            {-} PreemptionSuccessFlow [✓]
                --> ReactToSoundProxy [✓]
                --> EnsureAttentionManagerReady [✓]
                --> ResumeNavigation [✓]
                --> ClearHotwordEvent [✓] -- 'hotword_event' found and removed
    [-] L3_AdmissionAndExecution [-]    ← L3 preempted (INVALID)
        --> NavigateToGroupPose [*]     ← Navigation state preserved
```

**Resultado:** ✅ L2 toma control. L3 pierde el tick (status=INVALID). `NavigateToGroupPose` mantiene su estado RUNNING interno para resume.

---

## Escenario 2 — L2 termina → Retorno y Reanudación de L3

**Condición inicial:** `hotword_event=False` (L2 no se activa), L3 admitida via MissionAdmissionGate.

**Trigger:** After L2 interaction completes, `hotword_event` cleared (tick 4 → 5).

**Log evidencia (tick 4 & 5):**
```
[ INFO] LayerReporter[L2]: [LayerTransition] L2 → L2 | HumanPreemption (hotword) [hotword_event=False]

[o] Priorities [*]
    {-} L2_HumanPreemption [✕]          ← L2 falló (no hay hotword)
        --> HotwordBeforePause? [✕]
    [-] L3_AdmissionAndExecution [*]    ← L3 recupera el tick
        --> MissionAdmissionGate [✓]
        -^- MissionStatusTracker [*]
            {-} L3_Mission [*]          ← L3 reanuda desde donde estaba
                --> NavigateToGroupPose [*]  ← Sigue navegando
```

**Resultado:** ✅ L3 reanuda automáticamente gracias a `memory=True` en `L3_Mission`. El `WithPreemptionContract` detecta el re-inicio via `initialise()` y registra el estado como `RESUMED`.

---

## Escenario 3 — L1 crítico forzando abort seguro de L3 y L2

**Condición inicial:** L3 Mission en RUNNING, `battery_critical=False`.

**Trigger:** `battery_critical = True` (tick 6).

**Log evidencia (tick 6):**
```
[ INFO] LayerReporter[L1]: [LayerTransition] L1 → L1 | Survival (critical battery) [battery_critical=True]

[o] Priorities [*]
    {-} L1_Survival [*]                 ← L1 toma control
        --> IsBatteryCritical? [✓]      -- 'battery_critical' comparison succeeded [v: True][e: True]
        -^- DockTimeout [*]             ← Secuencia de docking iniciada
            --> NavigateToDock [*]      ← Navegando al dock
    {-} L2_HumanPreemption [-]          ← L2 preempted (INVALID)
    [-] L3_AdmissionAndExecution [-]    ← L3 preempted (INVALID)
        --> NavigateToGroupPose [*]     ← Estado preservado por memory=True
```

**Resultado:** ✅ L1 toma control inmediatamente. L2 y L3 son interrumpidos de forma limpia (reciben `stop(INVALID)`). El `WithPreemptionContract` captura este evento, registra `PreemptionState.PREEMPTED` y podría ejecutar el callback `on_preempt` (ej. publicar unpause Nav2).

---

## Notas de Implementación

- El `WithPreemptionContract` **sí** se activa correctamente en cada `stop(INVALID)`, pero en los logs de esta prueba el `on_preempt` callback es `None` (no definido aún en el constructor de los nodos), por lo que el efecto visible es únicamente el cambio de estado interno.
- En producción, el callback `on_preempt` podría publicar en `/nav2/pause` para pausar Nav2 de forma explícita cuando L3 es interrumpido.
- El mecanismo de resume de `memory=True` en `py_trees` funciona de forma nativa: el Selector `Priorities` con `memory=False` vuelve a evaluar desde L1→L2→L3 cada tick, y cuando L2 falla, L3 recupera el tick automáticamente. El `WithPreemptionContract` enriquece este mecanismo con callbacks explícitos.

## Comando para Repetir

```bash
cd /home/pablo/google_drive/Universidad/MAPIR/Sancho/sancho_robot/ros2_ws
source /opt/ros/humble/setup.bash && source install/setup.bash
python3 src/sancho_behavior/scripts/test_preemption.py
```
