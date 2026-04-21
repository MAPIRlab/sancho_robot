import rclpy
from rclpy.qos import QoSProfile

import py_trees
import py_trees_ros

from std_msgs.msg import Float32, String

from sancho_behavior.trees.react_to_sound_tree import create_reaction_subtree
from sancho_behavior.trees.interaction_tree import create_interaction_subtree
from sancho_behavior.behaviors.sensors import OdomYawToBlackboard

def create_root() -> py_trees.behaviour.Behaviour:
    """Creates the main behavior tree"""
    
    root = py_trees.composites.Parallel(
        name="Sancho Root", 
        policy=py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=False)
    )

    # --- BRANCH 1: TOPICS TO BLACKBOARD ---
    topics2bb = py_trees.composites.Parallel(
        name="Topics2BB",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=False)
    )

    doa2bb = py_trees_ros.subscribers.ToBlackboard(
        name="DoA2BB",
        topic_name="/sancho_audio/doa",
        topic_type=Float32,
        qos_profile=QoSProfile(depth=10),
        blackboard_variables={"last_angle": "data"},
        initialise_variables={"last_angle": 0.0},
        clearing_policy=py_trees.common.ClearingPolicy.NEVER
    )
    
    hotword2bb = py_trees_ros.subscribers.EventToBlackboard(
        name="Hotword2BB",
        topic_name="/voice_events/hotword_detected",
        variable_name="hotword_event",
        qos_profile=QoSProfile(depth=10)
    )

    odom_yaw2bb = OdomYawToBlackboard()

    speaker2bb = py_trees_ros.subscribers.ToBlackboard(
        name="Speaker2BB",
        topic_name="/active_speaker_info",
        topic_type=String,
        qos_profile=QoSProfile(depth=10),
        blackboard_variables={"speaker_info_json": "data"},
        initialise_variables={"speaker_info_json": '{"id": "0", "name": "amigo"}'},
        clearing_policy=py_trees.common.ClearingPolicy.NEVER
    )

    # --- BRANCH 2: PRIORITIES ---
    priorities = py_trees.composites.Selector(name="Priorities", memory=False)
    reaction_to_sound = create_reaction_subtree()
    interaction = create_interaction_subtree()
    idle = py_trees.behaviours.Running(name="Idle")

    # -- Build Tree ---
    root.add_children([topics2bb, priorities])
    topics2bb.add_children([doa2bb, hotword2bb, odom_yaw2bb, speaker2bb])
    priorities.add_children([reaction_to_sound, interaction, idle])
    
    return root

def main():
    rclpy.init()

    # -- Global Configuration ---
    config_bb = py_trees.blackboard.Client(name="GlobalConfig")
    
    # Register BB variables
    config_bb.register_key(key="config/max_head_angle", access=py_trees.common.Access.WRITE)
    config_bb.register_key(key="config/far_angle_limit", access=py_trees.common.Access.WRITE)
    
    # Set config values
    config_bb.set("config/max_head_angle", 90.0)
    config_bb.set("config/far_angle_limit", 60.0)

    # --- Tree Creation ---
    root = create_root()
    tree = py_trees_ros.trees.BehaviourTree(
        root=root, 
        unicode_tree_debug=True
    )
    tree.visitors.append(py_trees.visitors.DisplaySnapshotVisitor(display_blackboard=True))

    try:
        tree.setup(timeout=15.0)
        print("\n--- Main Behavior Tree Initialized Successfully ---")
        tree.tick_tock(period_ms=100)
        rclpy.spin(tree.node)
    except (KeyboardInterrupt, py_trees_ros.exceptions.NotReadyError):
        print("\nStopping behavior tree execution...")
    finally:
        tree.shutdown()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()