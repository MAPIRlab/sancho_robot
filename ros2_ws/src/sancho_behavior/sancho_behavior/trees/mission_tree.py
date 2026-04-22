import py_trees
from py_trees.composites import Sequence
from sancho_behavior.behaviors.navigation import NavigateToGroupPose
from sancho_behavior.behaviors.capability_control import CapabilityEnable, CapabilitySetMode
from sancho_behavior.behaviors.lifecycle_actions import ActivateNode, DeactivateNode
from sancho_behavior.behaviors.interaction import WaitForSocialInteraction
from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.preemption_contract import WithPreemptionContract

def create_mission_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 3: Mission

    Handles the orchestrator logic: HasGroupWaypoint -> Pause Detectors ->
    Navigate -> Socialize.

    Children (Sequence, memory=True):
        1. LayerReporter  — BTA-002: writes active_layer="L3" every tick.
        2. HasWaypoint?   — gate: only proceeds when a pose is on the BB.
        3-8. (navigation/socialisation sequence)

    Note (BTA-050):
        Mission admission policy (battery/cooldown/boundary rules) is handled
        in main_tree.py by MissionAdmissionGate. This subtree stays focused on
        mission execution semantics only.
    """
    mission_root = Sequence(name="L3_Mission", memory=True)

    # BTA-002: Reporter placed first so it executes whenever L3 is ticked.
    reporter = LayerReporter(
        layer="L3",
        reason_key="mission/active",
        reason_label="mission_active",
    )

    # Condition: DO we have a group waypoint?
    has_waypoint_check = py_trees.behaviours.CheckBlackboardVariableExists(
        name="HasWaypoint?",
        variable_name="group_waypoint_pose"
    )

    # Deactivate group detection during navigation
    deactivate_waypoint_node = DeactivateNode(name="DeactivateGroupWaypoint", node_name="group_waypoint_generator_node")

    # Navigate
    navigate = NavigateToGroupPose(name="NavigateToGroupPose")

    # Socialize
    tracking_mode_mission = CapabilitySetMode(
        name="TrackingModeMission",
        topic="/attention_manager/capability/tracking/set_mode",
        mode="active",
    )
    tracking_enable_mission = CapabilityEnable(
        name="EnableTrackingMission",
        service_name="/attention_manager/capability/tracking/enable",
    )
    activate_social = ActivateNode(name="ActivateInteractionManager", node_name="interaction_manager")
    
    # Wait for social interaction to finish
    wait_for_social = WaitForSocialInteraction(name="WaitForSocialInteraction")
    
    # After social is done, deactivate social and activate group detection
    tracking_mode_standby = CapabilitySetMode(
        name="TrackingModeMissionStandby",
        topic="/attention_manager/capability/tracking/set_mode",
        mode="standby",
    )
    deactivate_social = DeactivateNode(name="DeactivateInteractionManager", node_name="interaction_manager")
    activate_waypoint_node = ActivateNode(name="ActivateGroupWaypoint", node_name="group_waypoint_generator_node")

    # Clear waypoint from blackboard so we wait for a new one
    clear_waypoint = py_trees.behaviours.UnsetBlackboardVariable(name="ClearWaypoint", key="group_waypoint_pose")

    mission_root.add_children([
        reporter,
        has_waypoint_check,
        deactivate_waypoint_node,
        navigate,
        tracking_mode_mission,
        tracking_enable_mission,
        activate_social,
        wait_for_social,
        tracking_mode_standby,
        deactivate_social,
        activate_waypoint_node,
        clear_waypoint
    ])

    return WithPreemptionContract(
        child=mission_root,
        name="L3_Mission_Preemptable",
        resumable=True
    )
