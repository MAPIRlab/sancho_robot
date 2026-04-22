import py_trees
import operator
from py_trees.composites import Sequence
from py_trees.behaviours import CheckBlackboardVariableValue

# Ensure registry side-effect for ProxySubtreeBehavior factories.
from sancho_behavior.trees import react_to_sound_tree as _react_to_sound_registry  # noqa: F401

from sancho_behavior.behaviors.proxy_subtree import ProxySubtreeBehavior
from sancho_behavior.behaviors.capability_control import (
    CapabilityDisable,
    CapabilityEnable,
    CapabilitySetMode,
)
from sancho_behavior.behaviors.navigation import PauseNavigation, ResumeNavigation
from sancho_behavior.behaviors.layer_reporter import LayerReporter
from sancho_behavior.behaviors.preemption_checks import EnsureAttentionManagerReady
from sancho_behavior.behaviors.preemption_contract import WithPreemptionContract

def create_preemption_subtree() -> py_trees.behaviour.Behaviour:
    """
    Level 2: Human Preemption

    Reacts to hotwords: pauses navigation, handles the interruption flow,
    validates attention-manager handshake, then resumes navigation.

    BTA-020:
        Hotword gate is evaluated before PauseNavigation.
    BTA-021:
        ResumeNavigation is executed on both success and failure paths after
        pause has happened.
    BTA-022:
        Replaces the old stub with a real handshake against
        /attention_manager/interaction_finished.
    """
    # BTA-002: Reporter placed first so it executes whenever L2 is ticked.
    reporter = LayerReporter(
        layer="L2",
        reason_key="hotword_event",
        reason_label="hotword_event",
    )

    preemption_root = Sequence(name="L2_HumanPreemption", memory=True)

    # BTA-020: Gate L2 before any side effect (e.g. pausing Nav2).
    check_hotword = CheckBlackboardVariableValue(
        name="HotwordBeforePause?",
        check=py_trees.common.ComparisonExpression(
            variable="hotword_event",
            value=True,
            operator=operator.eq,
        ),
    )

    # Pause Navigation properly via lifecycle
    stop_nav = PauseNavigation(name="PauseNavigation")

    # The pure reaction to sound logic is encapsulated in its own subtree
    # to maintain a clear hierarchical structure.
    # BTA-073: Use proxy subtree to encapsulate the reaction flow.
    reaction_subtree = ProxySubtreeBehavior(
        name="ReactToSoundProxy",
        subtree_id="react_to_sound"
    )

    # BTA-022: Real readiness handshake with attention manager endpoint.
    attention_manager_ready = EnsureAttentionManagerReady(
        name="EnsureAttentionManagerReady",
        service_name="/attention_manager/interaction_finished",
        timeout_sec=0.3,
    )

    # BTA-021: explicit resume on success path.
    resume_nav_success = ResumeNavigation(name="ResumeNavigation")
    clear_hotword_success = py_trees.behaviours.UnsetBlackboardVariable(
        name="ClearHotwordEvent",
        key="hotword_event",
    )

    success_flow = Sequence(name="PreemptionSuccessFlow", memory=True)
    success_flow.add_children([
        CapabilitySetMode(
            name="TrackingModePreemption",
            topic="/attention_manager/capability/tracking/set_mode",
            mode="active",
        ),
        CapabilityEnable(
            name="EnableTrackingPreemption",
            service_name="/attention_manager/capability/tracking/enable",
        ),
        reaction_subtree,
        attention_manager_ready,
        resume_nav_success,
        CapabilitySetMode(
            name="TrackingModeStandby",
            topic="/attention_manager/capability/tracking/set_mode",
            mode="standby",
        ),
        clear_hotword_success,
    ])

    # BTA-021: explicit resume on failure path to avoid leaving Nav2 paused.
    resume_nav_failure = ResumeNavigation(name="ResumeNavigationOnFailure")
    clear_hotword_failure = py_trees.behaviours.UnsetBlackboardVariable(
        name="ClearHotwordOnFailure",
        key="hotword_event",
    )
    mark_failure = py_trees.behaviours.Failure(name="PreemptionFailure")

    failure_cleanup = Sequence(name="PreemptionFailureCleanup", memory=False)
    failure_cleanup.add_children([
        resume_nav_failure,
        CapabilityDisable(
            name="DisableTrackingOnFailure",
            service_name="/attention_manager/capability/tracking/disable",
        ),
        clear_hotword_failure,
        mark_failure,
    ])

    preemption_flow = py_trees.composites.Selector(
        name="PreemptionFlow",
        memory=False,
    )
    preemption_flow.add_children([success_flow, failure_cleanup])

    preemption_root.add_children([
        reporter,
        check_hotword,
        stop_nav,
        preemption_flow,
    ])

    return WithPreemptionContract(
        child=preemption_root,
        name="L2_HumanPreemption_Preemptable",
        resumable=True
    )
