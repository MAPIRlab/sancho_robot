import py_trees
import py_trees_ros
import operator
from ..behaviors.interaction import ListenToUser, GenerateLLMResponse, RespondUser, SetAudioSessionBehavior, CheckSilence
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
    interaction_root = py_trees.composites.Sequence(name="InteractionRoot", memory=True)

    # 1. State Initialisation
    init_state = py_trees.composites.Sequence(name="InitState", memory=True)
    init_state.add_children([
        py_trees.behaviours.SetBlackboardVariable(
            name="ResetFinished", variable_name="interaction_finished", variable_value=False, overwrite=True
        ),
        py_trees.behaviours.SetBlackboardVariable(
            name="SetEngaged", variable_name="is_engaged", variable_value=True, overwrite=True
        )
    ])

    # 2. Tracking Subtree
    tracking_parallel = py_trees.composites.Parallel(
        name="ActiveTracking", policy=py_trees.common.ParallelPolicy.SuccessOnAll()
    )
    tracking_parallel.add_children([ManageFaceTracker(), UpdateTrackingTarget()])

    # 3. One Conversation Turn (Sequence)
    conversation_turn = py_trees.composites.Sequence(name="ConversationTurn", memory=True)
    conversation_turn.add_children([
        SetAudioSessionBehavior(active=True),
        SetFaceMode("listening"),
        ListenToUser(name="ListenToUser", timeout_sec=10.0),
        SetAudioSessionBehavior(active=False),
        
        # --- NEW: Intercept silence before triggering the LLM ---
        CheckSilence(name="CheckSilence"), 
        
        SetFaceMode("thinking"),
        GenerateLLMResponse(),
        SetFaceMode("speaking"),
        RespondUser(text_bb_key="ai_response_text"),
    ])

    # 4. The Conversation Loop
    is_finished_check = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsFinished?",
        check=py_trees.common.ComparisonExpression("interaction_finished", True, operator=operator.eq)
    )

    conversation_loop = py_trees.composites.Selector(name="ConversationLoop", memory=False)
    conversation_loop.add_children([
        is_finished_check,
        py_trees.decorators.Repeat(name="RepeatTurn", child=conversation_turn, num_success=-1)
    ])

    # 5. Parallel interaction (Tracking + Conversation)
    interaction_tasks = py_trees.composites.Parallel(
        name="InteractionTasks",
        policy=py_trees.common.ParallelPolicy.SuccessOnOne(), 
        children=[tracking_parallel, conversation_loop]
    )

    # --- NEW: Guarantee cleanup runs even if the loop fails due to silence ---
    safe_interaction_tasks = py_trees.decorators.FailureIsSuccess(
        name="EnsureCleanupRuns",
        child=interaction_tasks
    )

    # 6. Cleanup
    cleanup = py_trees.composites.Sequence(name="Cleanup", memory=True)
    cleanup.add_children([
        SetFaceMode("idle"),
        py_trees.behaviours.SetBlackboardVariable(
            name="ClearEngaged", variable_name="is_engaged", variable_value=False, overwrite=True
        )
    ])

    interaction_root.add_children([
        init_state,
        safe_interaction_tasks,
        cleanup
    ])

    return interaction_root