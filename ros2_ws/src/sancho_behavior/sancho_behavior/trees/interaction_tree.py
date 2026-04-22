import operator
import py_trees
from py_trees.composites import Sequence

from sancho_behavior.behaviors.tracking import ManageFaceTracker, UpdateTrackingTarget
from sancho_behavior.behaviors.factories import SubtreeRegistry

# ==============================================================================
# MOCKS (As requested by user for standalone proxy migration)
# ==============================================================================
class MockSetFaceMode(py_trees.behaviours.Success):
    def __init__(self, mode: str):
        super().__init__(name=f"MockSetFaceMode({mode})")

class MockListenToUser(py_trees.behaviours.Success):
    def __init__(self):
        super().__init__(name="MockListenToUser")

class MockGenerateLLMResponse(py_trees.behaviours.Success):
    def __init__(self):
        super().__init__(name="MockGenerateLLMResponse")

class MockRespondUser(py_trees.behaviours.Success):
    def __init__(self):
        super().__init__(name="MockRespondUser")
# ==============================================================================

@SubtreeRegistry.register("interaction")
def create_interaction_subtree(name: str = "Interaction", config: dict = None) -> py_trees.behaviour.Behaviour:
    """
    Creates the branch that manages active face tracking.
    BTA-070: This subtree is now integrated via ProxySubtreeBehavior.
    """
    interaction_seq = py_trees.composites.Sequence(name=name, memory=False)
    
    # Condition to enter this branch
    is_engaged = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsEngaged?",
        check=py_trees.common.ComparisonExpression("is_engaged", True, operator=operator.eq)
    )

    handle_interaction_end = py_trees.composites.Selector(name="HandleInteractionEnd", memory=False)
    
    interaction_tasks = py_trees.composites.Parallel(
        name="InteractionTasks",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=False)
    )

    # Parallel node to handle lifecycle and target updates simultaneously
    tracking_parallel = py_trees.composites.Parallel(
        name="ActiveTracking",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=False),
    )

    conversation = py_trees.composites.Sequence(name="Conversation", memory=True)

    conversation.add_children([
        MockSetFaceMode("listening"),
        MockListenToUser(),             # Fails if timeout/silence -> drops out of conversation
        MockSetFaceMode("thinking"),
        MockGenerateLLMResponse(),
        MockSetFaceMode("speaking"),
        # Optionally add another SetFaceMode(blackboard.ai_emotion) here if you want color!
        MockRespondUser(),
        MockSetFaceMode("idle")
    ])

    reset_engaged = py_trees.behaviours.SetBlackboardVariable(
        name="ResetEngaged",
        variable_name="is_engaged",
        variable_value=False,
        overwrite=True
    )
    
    # Build Tree
    interaction_seq.add_children([is_engaged, handle_interaction_end])
    handle_interaction_end.add_children([interaction_tasks, MockSetFaceMode("idle"), reset_engaged])
    interaction_tasks.add_children([tracking_parallel, conversation])
    tracking_parallel.add_children([
        ManageFaceTracker(),
        UpdateTrackingTarget()
    ])

    return interaction_seq