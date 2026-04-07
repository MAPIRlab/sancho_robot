import py_trees
import py_trees_ros
import operator
from behaviors.sound import IsAngleFar, LockAngle, SpinBaseToSound, RotateHeadToSound
from sancho_interfaces.action import RotateHead

def create_subtree() -> py_trees.behaviour.Behaviour:
    # 1. Raíz del subárbol: Secuencia con memoria para no repetir pasos si un nodo queda en RUNNING
    root = py_trees.composites.Sequence(name="OrientateToSound", memory=True)

    # 2. Condición: ¿Han dicho la hotword?
    check_hotword = py_trees.behaviours.CheckBlackboardVariableValue(
        name="Hotword?",
        check=py_trees.common.ComparisonExpression("hotword_event", True, operator=operator.eq)
    )

    # 3. Decisión de movimiento
    turn_decision = py_trees.composites.Selector(name="DecideMovement", memory=False)

    # Rama: Sonido Lejano (Girar base y centrar cabeza)
    turn_far_seq = py_trees.composites.Sequence(name="TurnFar", memory=True)
    move_both_parallel = py_trees.composites.Parallel(
        name="ParallelHeadBase", 
        policy=py_trees.common.ParallelPolicy.SuccessOnAll()
    )
    center_goal = RotateHead.Goal(target_angle_deg=0.0, timeout_sec=5.0)
    center_head = py_trees_ros.action_clients.FromConstant(
        name="CenterHead", action_type=RotateHead, action_name="/head_controller/rotate", action_goal=center_goal
    )
    move_both_parallel.add_children([SpinBaseToSound(), center_head])
    turn_far_seq.add_children([IsAngleFar(limit=90.0), move_both_parallel])

    # Rama: Sonido Cercano (Solo mover cabeza)
    turn_near_seq = py_trees.composites.Sequence(name="TurnNear", memory=True)
    turn_near_seq.add_child(RotateHeadToSound())

    turn_decision.add_children([turn_far_seq, turn_near_seq])

    # 4. Limpieza: Resetear la hotword para la siguiente vez
    clear_hotword = py_trees.behaviours.SetBlackboardVariable(
        name="ClearHotword", variable_name="hotword_event", variable_value=False, overwrite=True
    )

    # Montaje final del subárbol
    root.add_children([check_hotword, LockAngle(), turn_decision, clear_hotword])
    return root