import math

import py_trees
import py_trees_ros
from py_trees.blackboard import Client

from nav2_msgs.action import Spin

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

class SpinBaseToSound(py_trees_ros.action_clients.FromBlackboard):
    def __init__(self, name="SpinBaseToSound"):
        super().__init__(
            name=name,
            action_type=Spin,
            action_name="/spin",
            key="spin_goal"
        )
        self.blackboard.register_key("target_angle", access=py_trees.common.Access.READ)
        self.blackboard.register_key("spin_goal", access=py_trees.common.Access.WRITE)
    
    def initialise(self):
        angle_deg = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0
        
        goal = Spin.Goal()
        goal.target_yaw = math.radians(angle_deg)
        
        self.blackboard.spin_goal = goal
        
        super().initialise()

class RotateHeadToSound(py_trees_ros.action_clients.FromBlackboard):
    def __init__(self, name="RotateHeadToSound"):
        super().__init__(
            name=name,
            action_type=RotateHead,
            action_name="/head_controller/rotate",
            key="head_goal"
        )
        self.blackboard.register_key("target_angle", access=py_trees.common.Access.READ)
        self.blackboard.register_key("head_goal", access=py_trees.common.Access.WRITE)
    
    def initialise(self):
        angle_deg = self.blackboard.target_angle if self.blackboard.exists("target_angle") else 0.0
        
        goal = RotateHead.Goal()
        goal.target_angle_deg = angle_deg
        goal.timeout_sec = 5.0
        self.blackboard.head_goal = goal
        
        super().initialise()

class TurnToSound(py_trees_ros.action_clients.FromBlackboard):
    def __init__(self, name="TurnToSound"):
        super().__init__(
            name=name,
            action_type=TurnToAngle,
            action_name='/attention_controller/turn_to_angle',
            key='turn_goal'
        )
        self.blackboard.register_key("absolute_target_angle", access=py_trees.common.Access.READ)
        self.blackboard.register_key("turn_goal", access=py_trees.common.Access.WRITE)
    
    def initialise(self):
        angle_deg = self.blackboard.absolute_target_angle if self.blackboard.exists("absolute_target_angle") else 0.0
        
        goal = TurnToAngle.Goal()
        goal.absolute_target_angle_deg = angle_deg
        self.blackboard.turn_goal = goal

        return super().initialise()
