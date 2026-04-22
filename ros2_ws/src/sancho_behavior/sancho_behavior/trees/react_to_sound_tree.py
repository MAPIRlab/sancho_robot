import py_trees

from sancho_behavior.behaviors.sound import IsAngleFar, LockTarget, RotateHeadToSound, TurnToSound
from sancho_behavior.behaviors.interaction import GreetUser, IdentifyCentralTarget
from sancho_behavior.behaviors.factories import SubtreeRegistry


@SubtreeRegistry.register("react_to_sound")
def create_reaction_subtree(name: str = "ReactToSound", config: dict = None) -> py_trees.behaviour.Behaviour:
    """
    Pure reaction subtree for L2 once preemption has already been gated.

    The hotword guard lives in preemption_tree.py (BTA-020), so this subtree
    only handles orientation and short social acknowledgement.
    """
    root = py_trees.composites.Sequence(name=name, memory=True)

    turn_decision = py_trees.composites.Selector(name="DecideMovement", memory=True)

    turn_far_seq = py_trees.composites.Sequence(name="TurnFar", memory=True)

    stabilize_camera = py_trees.timers.Timer(name="StabilizeCamera", duration=1.0) # 1 second delay

    set_engaged = py_trees.behaviours.SetBlackboardVariable(
        name="SetEngaged",
        variable_name="is_engaged",
        variable_value=True,
        overwrite=True
    )

    # --- Build Tree ---
    root.add_children([
        LockTarget(),
        turn_decision,
        stabilize_camera,
        IdentifyCentralTarget(),
        GreetUser(),
        set_engaged
    ])
    turn_decision.add_children([turn_far_seq, RotateHeadToSound()])
    turn_far_seq.add_children([IsAngleFar(), TurnToSound()])

    return root