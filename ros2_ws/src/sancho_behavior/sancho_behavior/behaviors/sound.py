import math

import py_trees
import py_trees_ros
from py_trees.blackboard import Client

from sancho_interfaces.action import RotateHead, TurnToAngle

class IsAngleFar(py_trees.behaviour.Behaviour):
    def __init__(self, name="IsAngleFar?"):
        super().__init__(name)
        self.blackboard = Client(name=self.name)
        self.blackboard.register_key(key="config/far_angle_limit", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="target_angle", access=py_trees.common.Access.READ)

        self.limit = self.blackboard.get("config/far_angle_limit") if self.blackboard.exists("config/far_angle_limit") else 90.0
    
    def update(self):
        angle = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0

        return py_trees.common.Status.SUCCESS if abs(angle) > self.limit else py_trees.common.Status.FAILURE

class LockTarget(py_trees.behaviour.Behaviour):
    """Saves target angle (relative and absolute) to blackboard"""
    def __init__(self, name="LockTarget"):
        super().__init__(name)
        self.blackboard = Client(name=self.name)
        self.blackboard.register_key(key="last_angle", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_base_angle", access=py_trees.common.Access.READ)
        
        self.blackboard.register_key(key="target_angle", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="absolute_target_angle", access=py_trees.common.Access.WRITE)
        self.node = None

    def setup(self, **kwargs):
        self.node = kwargs['node']

    def update(self):
        relative_doa = self.blackboard.last_angle if self.blackboard.exists("last_angle") else 0.0
        current_base = self.blackboard.current_base_angle if self.blackboard.exists("current_base_angle") else 0.0
        
        # Relative angle
        self.blackboard.target_angle = relative_doa
        
        # Absolute target
        abs_target = current_base + relative_doa
        
        # Normalize between -180 and 180 degrees
        abs_target_norm = math.degrees(math.atan2(
            math.sin(math.radians(abs_target)), 
            math.cos(math.radians(abs_target))
        ))
        
        self.blackboard.absolute_target_angle = abs_target_norm
            
        return py_trees.common.Status.SUCCESS

class RotateHeadToSound(py_trees_ros.actions.ActionClient):
    def __init__(self, name="RotateHeadToSound"):
        self.action_goal = RotateHead.Goal()

        super().__init__(
            name=name,
            action_type=RotateHead,
            action_name="/head_controller/rotate",
            action_goal=self.action_goal
        )
        
        self.blackboard.register_key("target_angle", access=py_trees.common.Access.READ)
    
    def initialise(self):
        angle_deg = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0
        
        self.action_goal.target_angle_deg = angle_deg
        self.action_goal.timeout_sec = 5.0
        
        super().initialise()

class TurnToSound(py_trees_ros.actions.ActionClient):
    def __init__(self, name="TurnToSound"):
        self.action_goal = TurnToAngle.Goal()

        super().__init__(
            name=name,
            action_type=TurnToAngle,
            action_name='/attention_controller/turn_to_angle',
            action_goal=self.action_goal
        )
        self.blackboard.register_key("absolute_target_angle", access=py_trees.common.Access.READ)
    
    def initialise(self):
        angle_deg = self.blackboard.absolute_target_angle if self.blackboard.exists("absolute_target_angle") else 0.0
        self.action_goal.absolute_target_angle_deg = angle_deg

        return super().initialise()
