import py_trees
from sancho_behavior.behaviors.proxy_subtree import ProxySubtreeBehavior
#from sancho_behavior.trees import interaction_tree as _interaction_registry  # noqa: F401
from sancho_behavior.trees import interaction_tree
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

    interaction_subtree = interaction_tree.create_interaction_tree()

    # BTA-088: Wrap movement in a selector to make it non-fatal
    movement_gate = py_trees.composites.Selector(name="OptionalMovement", memory=True)
    movement_gate.add_children([
        turn_decision,
        py_trees.behaviours.Success(name="IgnoreMovementFailure")
    ])

    # BTA-089: Wrap identification in a selector to make it non-fatal
    identification_gate = py_trees.composites.Selector(name="OptionalIdentification", memory=True)
    identification_gate.add_children([
        IdentifyCentralTarget(),
        py_trees.behaviours.Success(name="IgnoreIdentificationFailure")
    ])

    # --- Build Tree ---
    root.add_children([
        LockTarget(),
        movement_gate,
        stabilize_camera,
        identification_gate,
        #GreetUser(),
        interaction_subtree
    ])
    turn_decision.add_children([
        turn_far_seq, 
        py_trees.decorators.Timeout(
            name="RotateHeadTimeout",
            child=RotateHeadToSound(),
            duration=5.0
        )
    ])
    turn_far_seq.add_children([
        IsAngleFar(), 
        py_trees.decorators.Timeout(
            name="TurnTimeout",
            child=TurnToSound(),
            duration=5.0
        )
    ])

    return root