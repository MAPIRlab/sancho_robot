import operator

import py_trees

from sancho_behavior.behaviors.tracking import ManageFaceTracker, UpdateTrackingTarget

def create_interaction_subtree() -> py_trees.behaviour.Behaviour:
    """Creates the branch that manages active face tracking."""
    engaged_seq = py_trees.composites.Sequence(name="Interaction", memory=False)
    
    # Condition to enter this branch
    is_engaged = py_trees.behaviours.CheckBlackboardVariableValue(
        name="IsEngaged?",
        check=py_trees.common.ComparisonExpression("is_engaged", True, operator=operator.eq)
    )
    
    # Parallel node to handle lifecycle and target updates simultaneously
    tracking_parallel = py_trees.composites.Parallel(
        name="ActiveTracking",
        policy=py_trees.common.ParallelPolicy.SuccessOnOne(),
    )
    
    tracking_parallel.add_children([
        ManageFaceTracker(),
        UpdateTrackingTarget()
    ])
    
    engaged_seq.add_children([is_engaged, tracking_parallel])
    return engaged_seq