import py_trees
import py_trees.decorators
from py_trees.composites import Sequence, Selector
from py_trees.behaviours import CheckBlackboardVariableValue, SetBlackboardVariable
import operator
import py_trees_ros
from sancho_interfaces.action import PlayTTS

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

    # ================= GATES =================

    battery_critical_check = CheckBlackboardVariableValue(
        name="IsBatteryCritical?",
        check=py_trees.common.ComparisonExpression(variable="battery_critical", value=True, operator=operator.eq)
    )

    is_charging_check = CheckBlackboardVariableValue(
        name="IsCharging?",
        check=py_trees.common.ComparisonExpression(variable="is_charging", value=True, operator=operator.eq)
    )

    has_greeted_check = CheckBlackboardVariableValue(
        name="HasGreeted?",
        check=py_trees.common.ComparisonExpression(variable="has_greeted_charging", value=True, operator=operator.eq)
    )

    # ================= CHARGING BRANCH =================
    
    greeting_goal = PlayTTS.Goal()
    greeting_goal.text = "Gracias por ponerme a cargar."
    greeting_tts = py_trees_ros.action_clients.FromConstant(
        name="GreetingTTS", action_type=PlayTTS, action_name="/play_tts", action_goal=greeting_goal, wait_for_server_timeout_sec=1.0 
    )

    set_greeted_flag = SetBlackboardVariable(
        name="SetGreetedFlag", variable_name="has_greeted_charging", variable_value=True, overwrite=True
    )

    # 1. Speak, then set the flag
    greeting_sequence = Sequence(name="Greeting_Sequence", memory=True)
    greeting_sequence.add_children([greeting_tts, set_greeted_flag])

    # 2. Skip speaking if the flag is already True
    check_greeted_selector = Selector(name="Check_Greeted", memory=False)
    check_greeted_selector.add_children([
        has_greeted_check,  
        greeting_sequence   
    ])

    # 3. Only run this whole logic if we are charging
    handle_charging_sequence = Sequence(name="Handle_Charging", memory=False)
    handle_charging_sequence.add_children([
        is_charging_check,
        check_greeted_selector
    ])

    # ================= DOCKING BRANCH =================

    navigate_to_dock = NavigateToDock(name="NavigateToDock")
    dock_with_timeout = py_trees.decorators.Timeout(
        child=navigate_to_dock, name="DockTimeout", duration=120.0,
    )

    sos_goal = PlayTTS.Goal()
    sos_goal.text = "Ayuda, ponme a cargar."
    request_charge_sos = py_trees_ros.action_clients.FromConstant(
        name="RequestChargeTTS", action_type=PlayTTS, action_name="/play_tts", action_goal=sos_goal, wait_for_server_timeout_sec=1.0 
    )

    # 4. Dock, then yell for help
    docking_sequence = Sequence(name="Docking_Sequence", memory=True)
    docking_sequence.add_children([
        dock_with_timeout,
        request_charge_sos,
    ])

    # ================= ROOT ROUTER =================

    # 5. Choose: Are we charging, or do we need to dock?
    charge_or_dock = Selector(name="Charge_Or_Dock", memory=False)
    charge_or_dock.add_children([
        handle_charging_sequence, 
        docking_sequence   
    ])

    # 6. Main entry point
    survival_root = Sequence(name="L1_Survival", memory=False)
    survival_root.add_children([
        reporter,
        battery_critical_check,
        charge_or_dock,
    ])

    return survival_root