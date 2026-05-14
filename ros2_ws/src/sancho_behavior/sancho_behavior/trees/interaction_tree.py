import py_trees
import py_trees_ros
import operator
from ..behaviors.interaction import ListenToUser, GenerateLLMResponse, RespondUser, SetAudioSessionBehavior
from ..behaviors.tracking import ManageFaceTracker, UpdateTrackingTarget

def SetFaceMode(mode):
    """Helper to set face mode via blackboard"""
    return py_trees.behaviours.SetBlackboardVariable(
        name=f"SetFace-{mode}",
        variable_name="face_mode",
        variable_value=mode,
        overwrite=True
    )

def create_interaction_tree():
    """
    Creates a self-contained subtree for human interaction.
    Manages its own lifecycle and provides a public 'is_engaged' flag.
    """
    
    # Root: A sequence that ensures we reset before looping and cleanup after
    interaction_root = py_trees.composites.Sequence(name="InteractionRoot", memory=True)

    # 1. State Initialisation
    init_state = py_trees.composites.Sequence(name="InitState", memory=True)
    init_state.add_children([
        # Internal flag for the loop
        py_trees.behaviours.SetBlackboardVariable(
            name="ResetFinished",
            variable_name="interaction_finished",
            variable_value=False,
            overwrite=True
        ),
        # Public flag for other branches to know we are busy
        py_trees.behaviours.SetBlackboardVariable(
            name="SetEngaged",
            variable_name="is_engaged",
            variable_value=True,
            overwrite=True
        )
    ])

    # 2. Tracking Subtree (Parallel to the conversation)
    tracking_parallel = py_trees.composites.Parallel(
        name="ActiveTracking",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll()
    )
    tracking_parallel.add_children([
        ManageFaceTracker(),
        UpdateTrackingTarget()
    ])

    # 3. One Conversation Turn (Sequence)
    conversation_turn = py_trees.composites.Sequence(name="ConversationTurn", memory=True)
    conversation_turn.add_children([
        SetAudioSessionBehavior(active=True),
        SetFaceMode("listening"),
        ListenToUser(name="ListenToUser", timeout_sec=10.0),
        SetAudioSessionBehavior(active=False),
        SetFaceMode("thinking"),
        GenerateLLMResponse(),
        SetFaceMode("speaking"),
        RespondUser(),
    ])

    # 4. The Conversation Loop
    is_finished_check = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsFinished?",
        check=py_trees.common.ComparisonExpression("interaction_finished", True, operator=operator.eq)
    )

    conversation_loop = py_trees.composites.Selector(name="ConversationLoop", memory=False)
    conversation_loop.add_children([
        is_finished_check,
        py_trees.decorators.Repeat(
            name="RepeatTurn",
            child=conversation_turn,
            num_success=-1
        )
    ])

    # 5. Parallel interaction (Tracking + Conversation)
    interaction_tasks = py_trees.composites.Parallel(
        name="InteractionTasks",
        policy=py_trees.common.ParallelPolicy.SuccessOnOne(), 
        children=[
            tracking_parallel,
            conversation_loop
        ]
    )

    # 6. Cleanup
    cleanup = py_trees.composites.Sequence(name="Cleanup", memory=True)
    cleanup.add_children([
        SetFaceMode("idle"),
        py_trees.behaviours.SetBlackboardVariable(
            name="ClearEngaged",
            variable_name="is_engaged",
            variable_value=False,
            overwrite=True
        )
    ])

    interaction_root.add_children([
        init_state,
        interaction_tasks,
        cleanup
    ])

    return interaction_root