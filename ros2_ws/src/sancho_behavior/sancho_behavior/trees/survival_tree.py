import py_trees
import py_trees.decorators
from py_trees.composites import Sequence
from py_trees.behaviours import CheckBlackboardVariableValue
import operator

from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.navigation import NavigateToDock


def create_survival_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 1: Survival (Homeostasis)

    Triggers when ``battery_critical`` is True on the blackboard.
    When active, aborts any ongoing mission and attempts auto-docking.

    Children (Sequence, memory=True):
        1. LayerReporter[L1]  — BTA-002: writes active_layer="L1" every tick.
        2. IsBatteryCritical? — gate: only proceeds when flag is True.
        3. DockTimeout        — BTA-010: Timeout(120s) wrapping NavigateToDock.
           └── NavigateToDock — real Nav2 action to config/dock_pose.

    Preemption contract:
        When battery_critical is False the Sequence immediately returns FAILURE
        (the gate node fails), giving control back to the parent Selector so
        L2-L4 can run normally. No side-effects are left behind.

    Docking contract (BTA-010):
        NavigateToDock reads ``config/dock_pose`` (initialised in main() with
        a safe default at the map origin). The Timeout decorator enforces a
        hard 120-second ceiling so a stuck robot cannot hold L1 indefinitely.
        If the timeout fires, the decorator returns FAILURE, which propagates
        up and causes L1 to yield. The BatteryMonitor's hysteresis prevents
        this from causing rapid re-entry unless the battery is genuinely below
        the critical threshold.
    """

    # BTA-002: Reporter placed first so it executes whenever L1 is ticked.
    reporter = LayerReporter(
        layer="L1",
        reason_key="battery_critical",
        reason_label="battery_critical",
    )

    # Gate: only allow the rest of the sequence to execute if battery is
    # critically low. When False, the Sequence returns FAILURE and the
    # parent Selector moves to the next layer (L2).
    battery_critical_check = CheckBlackboardVariableValue(
        name="IsBatteryCritical?",
        check=py_trees.common.ComparisonExpression(
            variable="battery_critical",
            value=True,
            operator=operator.eq
        )
    )

    # BTA-010: Real docking action with a 120-second hard timeout.
    # NavigateToDock reads config/dock_pose and sends a NavigateToPose goal.
    navigate_to_dock = NavigateToDock(name="NavigateToDock")
    dock_with_timeout = py_trees.decorators.Timeout(
        child=navigate_to_dock,
        name="DockTimeout",
        duration=120.0,
    )

    survival_root = Sequence(name="L1_Survival", memory=True)
    survival_root.add_children([
        reporter,
        battery_critical_check,
        dock_with_timeout,
    ])

    return survival_root
