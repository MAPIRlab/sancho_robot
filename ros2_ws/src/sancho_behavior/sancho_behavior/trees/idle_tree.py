import operator

import py_trees
from py_trees.composites import Selector, Sequence
from py_trees.behaviours import CheckBlackboardVariableValue

from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.idle_behaviors import IdleHeadSweep, EnergySavingStandby


def create_idle_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 4: Idle (default catch-all)

    The robot reaches L4 when no L1/L2/L3 condition is active. L4 is always
    interrumpible — the parent Selector (memory=False) will preempt it the
    moment any higher-priority layer becomes active.

    Children (Sequence, memory=True):
        1. LayerReporter[L4] — BTA-002: writes active_layer="L4" every tick.
        2. IdlePolicy (Selector, memory=False) — BTA-011: switches behaviour
           based on battery state.
           ├── DegradedIdle (Sequence, memory=False)
           │   ├── IsBatteryDegraded?  — gate: proceeds only when True.
           │   └── EnergySavingStandby — reduced-movement idle behaviour.
           └── IdleHeadSweep          — active exploration via head sweep.

    Battery-degraded policy (BTA-011):
        When battery_degraded=True the DegradedIdle branch succeeds at the
        gate check and stays RUNNING via EnergySavingStandby, effectively keeping
        the robot stationary (no costly exploration). When the battery recovers,
        the gate returns FAILURE, the Selector falls through to IdleHeadSweep.
    """

    # BTA-002: Reporter placed first.
    reporter = LayerReporter(
        layer="L4",
        reason_key=None,  # unconditional catch-all — no specific trigger key
    )

    # --- DegradedIdle branch (BTA-011) ---
    # Gate: only proceed into energy-saving mode when battery is degraded.
    is_degraded_check = CheckBlackboardVariableValue(
        name="IsBatteryDegraded?",
        check=py_trees.common.ComparisonExpression(
            variable="battery_degraded",
            value=True,
            operator=operator.eq
        )
    )
    # BTA-041: low-energy standby behaviour.
    energy_saving_standby = EnergySavingStandby(
        name="EnergySavingStandby",
        refresh_sec=12.0,
        rest_tilt_deg=-30.0,
    )

    degraded_idle = Sequence(name="DegradedIdle", memory=False)
    degraded_idle.add_children([is_degraded_check, energy_saving_standby])

    # --- Normal exploration branch ---
    # BTA-040: real, non-blocking and preemptible idle scan behaviour.
    idle_head_sweep = IdleHeadSweep(
        name="IdleHeadSweep",
        sweep_angles_deg=[-45.0, -15.0, 15.0, 45.0, 0.0],
        hold_sec=3.0,
        tilt_deg=-20.0,
    )

    # --- Policy Selector ---
    # memory=False: re-evaluates which branch to take every tick, so the robot
    # switches between energy-saving and normal exploration dynamically.
    idle_policy = Selector(name="IdlePolicy", memory=False)
    idle_policy.add_children([degraded_idle, idle_head_sweep])

    # --- Root ---
    idle_root = Sequence(name="L4_Idle", memory=True)
    idle_root.add_children([reporter, idle_policy])

    return idle_root
