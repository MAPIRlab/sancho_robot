import py_trees
import operator

from sancho_behavior.behaviors.sound import IsAngleFar, LockTarget, RotateHeadToSound, TurnToSound
from sancho_behavior.behaviors.interaction import GreetUser, IdentifyCentralTarget


def create_reaction_subtree() -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(name="ReactToSound", memory=True)

    check_hotword = py_trees.behaviours.CheckBlackboardVariableValue(
        name="Hotword?",
        check=py_trees.common.ComparisonExpression("hotword_event", True, operator=operator.eq)
    )

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
        check_hotword,
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