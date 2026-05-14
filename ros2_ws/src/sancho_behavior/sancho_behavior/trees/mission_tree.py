import py_trees
import operator
from py_trees.composites import Sequence
from sancho_behavior.behaviors.navigation import NavigateToGroupPose, SelectRandomTopoNode, NavigateToRoamingPose
from sancho_behavior.behaviors.lifecycle_actions import ActivateNode, DeactivateNode
from sancho_behavior.behaviors.interaction import WaitForSocialInteraction
from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.preemption_contract import WithPreemptionContract

def create_mission_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 3: Mission

    Handles the orchestrator logic. Supports multiple mission types via a Selector.
    """
    # Root of L3 execution. Must be memory=False so the Selector evaluates properly.
    mission_root = py_trees.composites.Sequence(name="L3_Mission", memory=False)

    # BTA-002: Reporter placed first so it executes whenever L3 is ticked.
    reporter = LayerReporter(
        layer="L3",
        reason_key="mission/active",
        reason_label="mission_active",
    )

    # The selector chooses which mission to run based on mission/type
    mission_selector = py_trees.composites.Selector(name="L3_Mission_Selector", memory=False)

    # -------------------------------------------------------------------------
    # Mission: Social Approach
    # -------------------------------------------------------------------------
    social_seq = py_trees.composites.Sequence(name="Social_Approach_Mission", memory=True)
    
    social_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsSocialMission?",
        check=py_trees.common.ComparisonExpression(
            variable="mission/type",
            value="social_approach",
            operator=operator.eq
        )
    )
    
    # Condition: DO we have a group waypoint? (Still required for social approach)
    has_waypoint_check = py_trees.behaviours.CheckBlackboardVariableExists(
        name="HasWaypoint?",
        variable_name="group_waypoint_pose"
    )

    # Deactivate group detection during navigation
    deactivate_waypoint_node = DeactivateNode(name="DeactivateGroupWaypoint", node_name="group_waypoint_generator_node")

    # Navigate
    navigate = NavigateToGroupPose(name="NavigateToGroupPose")

    # Socialize
    activate_social = ActivateNode(name="ActivateInteractionManager", node_name="interaction_manager")

    # Wait for social interaction to finish
    wait_for_social = WaitForSocialInteraction(name="WaitForSocialInteraction")

    # After social is done, restore waypoint detection
    deactivate_social = DeactivateNode(name="DeactivateInteractionManager", node_name="interaction_manager")
    activate_waypoint_node = ActivateNode(name="ActivateGroupWaypoint", node_name="group_waypoint_generator_node")

    # Clear waypoint from blackboard so we wait for a new one
    clear_waypoint = py_trees.behaviours.UnsetBlackboardVariable(name="ClearWaypoint", key="group_waypoint_pose")

    social_seq.add_children([
        social_guard,
        has_waypoint_check,
        deactivate_waypoint_node,
        navigate,
        activate_social,
        wait_for_social,
        deactivate_social,
        activate_waypoint_node,
        clear_waypoint
    ])

    # -------------------------------------------------------------------------
    # Mission: Continuous Random Roaming
    # -------------------------------------------------------------------------
    # Use memory=False so the guard is evaluated every tick, allowing mid-mission cancellation
    roaming_seq = py_trees.composites.Sequence(name="Random_Roaming_Mission", memory=False)
    
    roaming_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsRoamingMission?",
        check=py_trees.common.ComparisonExpression(
            variable="mission/request",
            value="roaming",
            operator=operator.eq
        )
    )
    
    select_topo_node = SelectRandomTopoNode(name="SelectRandomTopoNode")
    
    # Ignore individual navigation failures so roaming continues to the next node
    navigate_to_roaming = py_trees.decorators.FailureIsSuccess(
        name="IgnoreNavFailures",
        child=NavigateToRoamingPose(name="NavigateToRoamingPose")
    )
    
    # Inner loop body: Select -> Navigate
    roaming_loop_body = py_trees.composites.Sequence(name="RoamingLoopBody", memory=True)
    roaming_loop_body.add_children([
        select_topo_node,
        navigate_to_roaming
    ])
    
    # Loop forever as long as the guard passes
    continuous_roaming = py_trees.decorators.SuccessIsRunning(
        name="ContinuousRoaming",
        child=roaming_loop_body
    )
    
    roaming_seq.add_children([
        roaming_guard,
        continuous_roaming
    ])

    # -------------------------------------------------------------------------
    # Assembly
    # -------------------------------------------------------------------------
    mission_selector.add_children([social_seq, roaming_seq])
    mission_root.add_children([reporter, mission_selector])

    return WithPreemptionContract(
        child=mission_root,
        name="L3_Mission_Preemptable",
        resumable=True
    )
