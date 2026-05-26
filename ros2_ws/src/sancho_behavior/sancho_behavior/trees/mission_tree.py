import py_trees
import operator
from py_trees.composites import Sequence, Selector
from sancho_behavior.behaviors.navigation import (
    SelectRandomTopoNode,
    ResolveTargetNode,
    NavigateToPoseBehavior,
)
from sancho_behavior.behaviors.interaction import (
    RespondUser,
    SetFaceMode,
)
from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.preemption_contract import WithPreemptionContract


class MissionCancelGuard(py_trees.decorators.Decorator):
    """
    Decorator that aborts the child immediately when cancellation is requested.

    Normal operation:
      - Passes through the child's status (SUCCESS, FAILURE, RUNNING).
    On cancellation (mission/cancel_requested == True):
      - Returns FAILURE regardless of the child's status.

    This is a Decorator (not a Parallel child) so that:
      - The child's SUCCESS propagates correctly (mission completes).
      - The child's FAILURE propagates correctly (mission failed).
      - Cancellation overrides everything with FAILURE.
    """

    def __init__(self, child, name="MissionCancelGuard"):
        super().__init__(name=name, child=child)
        self.bb = self.attach_blackboard_client(name=name)
        self.bb.register_key(
            key="mission/cancel_requested", access=py_trees.common.Access.READ
        )

    def update(self):
        cancel = (
            self.bb.get("mission/cancel_requested")
            if self.bb.exists("mission/cancel_requested")
            else False
        )
        if cancel:
            return py_trees.common.Status.FAILURE
        return self.decorated.status


def create_mission_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 3: Mission
    Handles the orchestrator logic. Supports multiple mission types via a Selector.

    Architecture:
      - Each branch uses memory=False so the type-guard is re-evaluated every tick.
      - Execution bodies are wrapped in a MissionCancelGuard decorator that
        passes through the child's status normally but overrides with FAILURE
        when cancellation is requested.
      - MissionStatusTracker (in main_tree.py) is the sole writer of
        mission/status for terminal states (SUCCESS / FAILURE).
    """
    mission_root = py_trees.composites.Sequence(name="L3_Mission", memory=False)

    reporter = LayerReporter(
        layer="L3",
        reason_key="mission/active",
        reason_label="mission_active",
    )

    mission_selector = py_trees.composites.Selector(
        name="L3_Mission_Selector", memory=False
    )

    # -------------------------------------------------------------------------
    # Mission 1: Move and Talk
    # -------------------------------------------------------------------------
    speak_branch = py_trees.composites.Sequence(
        name="MoveAndTalk_Branch", memory=False
    )

    speak_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsMoveAndTalkMission?",
        check=py_trees.common.ComparisonExpression(
            "mission/request", "move_and_talk", operator.eq
        ),
    )

    # Actual mission logic
    speak_seq = py_trees.composites.Sequence(name="Speak_Sequence", memory=True)
    speak_seq.add_children(
        [
            # 1. Parameter Checks
            py_trees.behaviours.CheckBlackboardVariableExists(
                name="HasTargetPose?", variable_name="mission/target_pose"
            ),
            py_trees.behaviours.CheckBlackboardVariableExists(
                name="HasSpeechText?", variable_name="mission/speech_text"
            ),
            # 2. Resolve location name to coordinates
            ResolveTargetNode(
                name="TranslateLocationName", location_key="mission/target_pose"
            ),
            # 3. Navigate to destination
            NavigateToPoseBehavior(
                name="NavigateToDestination", pose_bb_key="mission/target_pose"
            ),
            # 4. Speak the payload
            SetFaceMode(mode="speaking", name="SetFaceSpeaking"),
            RespondUser(name="DeliverMessage", text_bb_key="mission/speech_text"),
            SetFaceMode(mode="idle", name="SetFaceIdle"),
        ]
    )

    # Cancel guard wraps the sequence — passes through SUCCESS/FAILURE normally,
    # overrides with FAILURE on cancellation
    speak_cancellable = MissionCancelGuard(
        child=speak_seq, name="SpeakCancelGuard"
    )

    speak_branch.add_children([speak_guard, speak_cancellable])

    # -------------------------------------------------------------------------
    # Mission 2: Continuous Random Roaming (Infinite)
    # -------------------------------------------------------------------------
    roaming_branch = py_trees.composites.Sequence(
        name="Random_Roaming_Branch", memory=False
    )

    roaming_guard = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsRoamingMission?",
        check=py_trees.common.ComparisonExpression(
            "mission/request", "roaming", operator.eq
        ),
    )

    roaming_loop_body = py_trees.composites.Sequence(
        name="RoamingLoopBody", memory=True
    )
    roaming_loop_body.add_children(
        [
            SelectRandomTopoNode(name="SelectRandomTopoNode"),
            py_trees.decorators.FailureIsSuccess(
                name="IgnoreNavFailures",
                child=NavigateToPoseBehavior(
                    name="NavigateToRoamingPose", pose_bb_key="roaming_goal_pose"
                ),
            ),
        ]
    )

    continuous_roaming = py_trees.decorators.SuccessIsRunning(
        name="ContinuousRoaming",
        child=roaming_loop_body,
    )

    # Cancel guard wraps roaming — the SuccessIsRunning keeps it RUNNING forever,
    # but the cancel guard can override with FAILURE to stop it
    roaming_cancellable = MissionCancelGuard(
        child=continuous_roaming, name="RoamingCancelGuard"
    )

    roaming_branch.add_children([roaming_guard, roaming_cancellable])

    # -------------------------------------------------------------------------
    # Assembly
    # -------------------------------------------------------------------------
    mission_selector.add_children([speak_branch, roaming_branch])
    mission_root.add_children([reporter, mission_selector])

    return WithPreemptionContract(
        child=mission_root,
        name="L3_Mission_Preemptable",
        resumable=True,
    )