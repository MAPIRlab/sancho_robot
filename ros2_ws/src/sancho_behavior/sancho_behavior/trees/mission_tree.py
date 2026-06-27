import py_trees
import operator
from py_trees.composites import Sequence, Selector, Parallel
from sancho_behavior.trees import interaction_tree
from sancho_behavior.behaviors.navigation import NavigateToGroupPose, SelectRandomTopoNode, ResolveTargetNode, NavigateToPoseBehavior
from sancho_behavior.behaviors.lifecycle_actions import ActivateNode, DeactivateNode
from sancho_behavior.behaviors.interaction import WaitForSocialInteraction, RespondUser, SetFaceMode, FormatActionMessage
from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.preemption_contract import WithPreemptionContract
from sancho_behavior.behaviors.action_recognition import PredictHumanAction

def report_status(status: str, name: str) -> py_trees.behaviour.Behaviour:
    """Helper to signal the Action Server that the mission ended."""
    return py_trees.behaviours.SetBlackboardVariable(
        name=name,
        variable_name="mission/status",
        variable_value=status,
        overwrite=True
    )

def create_mission_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 3: Mission
    Handles the orchestrator logic. Supports multiple mission types via a Selector.
    """
    mission_root = py_trees.composites.Sequence(name="L3_Mission", memory=False)

    reporter = LayerReporter(
        layer="L3",
        reason_key="mission/active",
        reason_label="mission_active",
    )

    mission_selector = py_trees.composites.Selector(name="L3_Mission_Selector", memory=False)

    # -------------------------------------------------------------------------
    # Mission 1: Social Approach
    # -------------------------------------------------------------------------
    # BRANCH: Combines the guard and the execution module
    social_branch = py_trees.composites.Sequence(name="Social_Approach_Branch", memory=False)
    
    social_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsSocialMission?",
        check=py_trees.common.ComparisonExpression("mission/request", "social_approach", operator.eq)
    )
    
    # EXECUTOR: Tries the happy path, falls back to recovery if it fails
    social_executor = py_trees.composites.Selector(name="Social_Executor", memory=False)

    # 1A. Happy Path
    social_seq = py_trees.composites.Sequence(name="Social_Sequence", memory=True)
    social_seq.add_children([
        py_trees.behaviours.CheckBlackboardVariableExists(name="HasWaypoint?", variable_name="group_waypoint_pose"),
        DeactivateNode(name="DeactivateGroupWaypoint", node_name="group_waypoint_generator_node"),
        NavigateToGroupPose(name="NavigateToGroupPose"),
        ActivateNode(name="ActivateInteractionManager", node_name="interaction_manager"),
        WaitForSocialInteraction(name="WaitForSocialInteraction"),
        DeactivateNode(name="DeactivateInteractionManager", node_name="interaction_manager"),
        ActivateNode(name="ActivateGroupWaypoint", node_name="group_waypoint_generator_node"),
        py_trees.behaviours.UnsetBlackboardVariable(name="ClearWaypoint", key="group_waypoint_pose"),
        report_status("SUCCESS", "SetSocialSuccess") # Wakes up the Action Server
    ])

    # 1B. Recovery Path
    social_recovery = py_trees.composites.Sequence(name="Social_Recovery", memory=True)
    social_recovery.add_children([
        ActivateNode(name="RestoreGroupWaypoint", node_name="group_waypoint_generator_node"),
        report_status("FAILURE", "SetSocialFailure"), # Informs Action Server
        py_trees.behaviours.Failure(name="PropagateSocialFailure") # Ensure the tree knows it failed
    ])

    social_executor.add_children([social_seq, social_recovery])
    social_branch.add_children([social_guard, social_executor])

    # -------------------------------------------------------------------------
    # Mission 2: Speak and Interact
    # -------------------------------------------------------------------------
    speak_branch = py_trees.composites.Sequence(name="Speak_Interact_Branch", memory=False)
    
    speak_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsSpeakInteractMission?",
        check=py_trees.common.ComparisonExpression("mission/request", "speak_and_interact", operator.eq)
    )

    speak_executor = py_trees.composites.Selector(name="Speak_Executor", memory=False)

    # 2A. Happy Path
    speak_seq = py_trees.composites.Sequence(name="Speak_Sequence", memory=True)
    speak_seq.add_children([
        # 1. Parameter Checks
        py_trees.behaviours.CheckBlackboardVariableExists(name="HasTargetPose?", variable_name="mission/target_pose"),
        py_trees.behaviours.CheckBlackboardVariableExists(name="HasSpeechText?", variable_name="mission/speech_text"),
        
        # 2. Traducir el nombre de la habitación a coordenadas X, Y
        ResolveTargetNode(name="TranslateLocationName", location_key="mission/target_pose"),
        
        # 3. Navigate to destination (ahora con el argumento pose_bb_key explícito)
        NavigateToPoseBehavior(name="NavigateToDestination", pose_bb_key="mission/target_pose"), 
        
        # 4. Speak the payload using your modified RespondUser
        SetFaceMode(mode="speaking", name="SetFaceSpeaking"),
        RespondUser(name="DeliverMessage", text_bb_key="mission/speech_text"), 
        SetFaceMode(mode="idle", name="SetFaceIdle"),
        
        # 5. Trigger the Interaction Manager to wait for a human response
        ActivateNode(name="ActivateInteraction", node_name="interaction_manager"),
        WaitForSocialInteraction(name="WaitForInteraction"),
        DeactivateNode(name="DeactivateInteraction", node_name="interaction_manager"),
        
        # 6. Report Success to the Orchestrator
        report_status("SUCCESS", "SetSpeakSuccess") 
    ])

    # 2B. Recovery Path
    speak_recovery = py_trees.composites.Sequence(name="Speak_Recovery", memory=True)
    speak_recovery.add_children([
        DeactivateNode(name="EnsureInteractionDeactivated", node_name="interaction_manager"),
        report_status("FAILURE", "SetSpeakFailure"),
        py_trees.behaviours.Failure(name="PropagateSpeakFailure")
    ])

    speak_executor.add_children([speak_seq, speak_recovery])
    speak_branch.add_children([speak_guard, speak_executor])

    # -------------------------------------------------------------------------
    # Mission 3: Continuous Random Roaming (Infinite)
    # -------------------------------------------------------------------------
    roaming_branch = py_trees.composites.Sequence(name="Random_Roaming_Branch", memory=False)
    
    roaming_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsRoamingMission?",
        check=py_trees.common.ComparisonExpression("mission/request", "roaming", operator.eq)
    )
    
    roaming_loop_body = py_trees.composites.Sequence(name="RoamingLoopBody", memory=True)
    roaming_loop_body.add_children([
        SelectRandomTopoNode(name="SelectRandomTopoNode"),
        py_trees.decorators.FailureIsSuccess(
            name="IgnoreNavFailures",
            child=NavigateToPoseBehavior(name="NavigateToRoamingPose", pose_bb_key="roaming_goal_pose")
        )
    ])
    
    continuous_roaming = py_trees.decorators.SuccessIsRunning(
        name="ContinuousRoaming",
        child=roaming_loop_body
    )
    
    roaming_branch.add_children([roaming_guard, continuous_roaming])

    # -------------------------------------------------------------------------
    # Mission 4: Action Recognition and Interaction
    # -------------------------------------------------------------------------
    action_branch = py_trees.composites.Sequence(name="Action_Interact_Branch", memory=False)
    
    #Create the Interaction subtree
    interaction_subtree = interaction_tree.create_interaction_tree()


    # 1. El Guard que activa esta misión específica
    action_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsActionMission?",
        check=py_trees.common.ComparisonExpression("mission/request", "action_recognition", operator.eq)
    )

    action_executor = py_trees.composites.Selector(name="Action_Executor", memory=False)

    # 2A. Happy Path
    action_seq = py_trees.composites.Sequence(name="Action_Sequence", memory=True)
    action_seq.add_children([
        py_trees.behaviours.CheckBlackboardVariableExists(name="HasTargetPose?_Action", variable_name="mission/target_pose"),
        
        # Navegación hacia el sujeto
        ResolveTargetNode(name="TranslateLocationName_Action", location_key="mission/target_pose"),
        NavigateToPoseBehavior(name="NavigateToDestination_Action", pose_bb_key="mission/target_pose"), 

        # Ejecutamos la predicción
        PredictHumanAction(name="AnalyzeUserAction"),

        # Preparamos el mensaje para que lo diga Sancho
        FormatActionMessage(name="FormatMessage"),
        
        # Cambiamos la UI de la cara de SANCHO a "speaking"
        SetFaceMode(mode="speaking", name="SetFaceSpeaking_Action"),

        # Interacción basada en la acción
        RespondUser(name="DeliverActionFeedback", text_bb_key="speech_message"), 

        # Cambiamos la UI de la cara de SANCHO a "idle"
        SetFaceMode(mode="idle", name="SetFaceIdle"),

        report_status("SUCCESS", "SetActionSuccess") 
    ])

    # 2B. Recovery Path (Manejo de errores si falla la navegación o la cámara)
    action_recovery = py_trees.composites.Sequence(name="Action_Recovery", memory=True)
    action_recovery.add_children([
        DeactivateNode(name="EnsureInteractionDeactivated", node_name="interaction_manager"),
        report_status("FAILURE", "SetActionFailure"),
        py_trees.behaviours.Failure(name="PropagateActionFailure")
    ])

    action_executor.add_children([action_seq, action_recovery])
    action_branch.add_children([action_guard, action_executor])


    # -------------------------------------------------------------------------
    # Assembly
    # -------------------------------------------------------------------------
    # Place all branches inside the selector
    mission_selector.add_children([social_branch, speak_branch, roaming_branch, action_branch])
    mission_root.add_children([reporter, mission_selector])

    return WithPreemptionContract(
        child=mission_root,
        name="L3_Mission_Preemptable",
        resumable=True
    )