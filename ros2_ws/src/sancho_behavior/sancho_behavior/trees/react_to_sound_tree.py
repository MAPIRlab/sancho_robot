import py_trees

from sancho_behavior.behaviors.sound import IsAngleFar, LockTarget, RotateHeadToSound, TurnToSound
from sancho_behavior.behaviors.interaction import GreetUser, IdentifyCentralTarget


def create_reaction_subtree() -> py_trees.behaviour.Behaviour:
    """
    Pure reaction subtree for L2 once preemption has already been gated.

    The hotword guard lives in preemption_tree.py (BTA-020), so this subtree
    only handles orientation and short social acknowledgement.
    """
    root = py_trees.composites.Sequence(name="ReactToSound", memory=True)

    turn_decision = py_trees.composites.Selector(name="DecideMovement", memory=True)

    turn_far_seq = py_trees.composites.Sequence(name="TurnFar", memory=True)

    # --- Build Tree ---
    root.add_children([
        LockTarget(),
        turn_decision,
        IdentifyCentralTarget(),
        GreetUser()
    ])
    turn_decision.add_children([turn_far_seq, RotateHeadToSound()])
    turn_far_seq.add_children([IsAngleFar(), TurnToSound()])

    return root