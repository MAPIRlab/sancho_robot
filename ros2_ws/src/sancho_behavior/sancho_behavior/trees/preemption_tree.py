import py_trees
import operator
from py_trees.composites import Sequence
from py_trees.behaviours import CheckBlackboardVariableValue

# Ensure registry side-effect for ProxySubtreeBehavior factories.
from sancho_behavior.trees import react_to_sound_tree

from sancho_behavior.behaviors.proxy_subtree import ProxySubtreeBehavior
from sancho_behavior.behaviors.layer_reporter import LayerReporter
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

    # The pure reaction to sound logic is encapsulated in its own subtree
    # to maintain a clear hierarchical structure.
    # BTA-073: Use proxy subtree to encapsulate the reaction flow.
    reaction_subtree = ProxySubtreeBehavior(
        name="ReactToSoundProxy",
        subtree_id="react_to_sound"
    )
    #reaction_subtree = react_to_sound_tree.create_reaction_subtree(name="ReactToSound")  # temporary direct call to ensure subtree is created for ProxySubtreeBehavior; can be removed once integrated into main tree

    clear_hotword_success = py_trees.behaviours.UnsetBlackboardVariable(
        name="ClearHotwordEvent",
        key="hotword_event",
    )

    success_flow = Sequence(name="PreemptionSuccessFlow", memory=True)
    success_flow.add_children([
        reaction_subtree,
        clear_hotword_success,
    ])

    clear_hotword_failure = py_trees.behaviours.UnsetBlackboardVariable(
        name="ClearHotwordOnFailure",
        key="hotword_event",
    )
    mark_failure = py_trees.behaviours.Failure(name="PreemptionFailure")

    failure_cleanup = Sequence(name="PreemptionFailureCleanup", memory=True)
    failure_cleanup.add_children([
        clear_hotword_failure,
        mark_failure,
    ])

    preemption_flow = py_trees.composites.Selector(
        name="PreemptionFlow",
        memory=True,
    )
    preemption_flow.add_children([success_flow, failure_cleanup])

    preemption_root.add_children([
        reporter,
        check_hotword,
        preemption_flow,
    ])

    return WithPreemptionContract(
        child=preemption_root,
        name="L2_HumanPreemption_Preemptable",
        resumable=True
    )
