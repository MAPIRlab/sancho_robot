import math

import py_trees
import py_trees_ros
from py_trees.blackboard import Client

from nav2_msgs.action import Spin
from sancho_interfaces.action import RotateHead

class IsAngleFar(py_trees.behaviour.Behaviour):
    def __init__(self, name="IsAngleFar", limit=90.0):
        super().__init__(name)
        self.limit = limit
        self.blackboard = Client(name=self.name)
        self.blackboard.register_key(key="target_angle", access=py_trees.common.Access.READ)
    def update(self):
        angle = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0
        return py_trees.common.Status.SUCCESS if abs(angle) > self.limit else py_trees.common.Status.FAILURE

class LockAngle(py_trees.behaviour.Behaviour):
    """Nodo síncrono que congela el ángulo justo en el momento en que se activa."""
    def __init__(self, name="LockAngle"):
        super().__init__(name)
        self.blackboard = Client(name=self.name)
        # Leemos el ángulo en vivo del sensor
        self.blackboard.register_key(key="last_angle", access=py_trees.common.Access.READ)
        # Escribimos en una variable segura
        self.blackboard.register_key(key="target_angle", access=py_trees.common.Access.WRITE)
        self.node = None

    def setup(self, **kwargs):
        self.node = kwargs['node']

    def update(self):
        # Tomamos la "foto" del ángulo actual
        angle = self.blackboard.last_angle if self.blackboard.exists("last_angle") else 0.0
        self.blackboard.target_angle = angle
        
        if self.node:
            self.node.get_logger().info(f"Ángulo congelado en {angle:.2f} grados. Ignorando ruido de motores.")
            
        return py_trees.common.Status.SUCCESS

class SpinBaseToSound(py_trees_ros.action_clients.FromBlackboard):
    def __init__(self, name="SpinBaseToSound"):
        super().__init__(
            name=name,
            action_type=Spin,
            action_name="/spin",
            key="spin_goal"
        )
        self.blackboard.register_key("target_angle", access=py_trees.common.Access.READ)
    
    def initialise(self):
        angle_deg = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0
        
        goal = Spin.Goal()
        goal.target_yaw = math.radians(angle_deg)
        
        self.blackboard.spin_goal = goal
        
        super().initialise()

class RotateHeadToSound(py_trees_ros.action_clients.FromBlackboard):
    def __init__(self, name="SpinBaseToSound"):
        super().__init__(
            name=name,
            action_type=RotateHead,
            action_name="/head_controller/rotate",
            key="head_goal"
        )
        self.blackboard.register_key("target_angle", access=py_trees.common.Access.READ)
    
    def initialise(self):
        angle_deg = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0
        
        goal = RotateHead.Goal()
        goal.target_angle_deg = angle_deg
        goal.timeout_sec = 5.0
        self.blackboard.head_goal = goal
        
        super().initialise()