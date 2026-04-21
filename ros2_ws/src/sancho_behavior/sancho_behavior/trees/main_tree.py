import rclpy
from rclpy.qos import QoSProfile

import py_trees
import py_trees_ros

from std_msgs.msg import Float32, String
from geometry_msgs.msg import PoseStamped, Quaternion
from sensor_msgs.msg import BatteryState

from sancho_behavior.behaviors.sensors import OdomYawToBlackboard
from sancho_behavior.trees.survival_tree import create_survival_subtree
from sancho_behavior.trees.preemption_tree import create_preemption_subtree
from sancho_behavior.trees.mission_tree import create_mission_subtree
from sancho_behavior.trees.idle_tree import create_idle_subtree
from sancho_behavior.behaviors.battery_monitor import BatteryMonitor
from sancho_behavior.behaviors.mission_arbitration import MissionAdmissionGate, MissionStatusTracker

def create_root() -> py_trees.behaviour.Behaviour:
    """Creates the main 4-priority hierarchical behavior tree"""

    root = py_trees.composites.Parallel(
        name="SanchoRoot", 
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

    waypoint2bb = py_trees_ros.subscribers.ToBlackboard(
        name="Waypoint2BB",
        topic_name="/group_waypoint",
        topic_type=PoseStamped,
        qos_profile=QoSProfile(depth=10),
        blackboard_variables={"group_waypoint_pose": ""},
        clearing_policy=py_trees.common.ClearingPolicy.ON_SUCCESS
    )

    battery2bb = py_trees_ros.subscribers.ToBlackboard(
        name="Battery2BB",
        topic_name="/battery_state",
        topic_type=BatteryState,
        qos_profile=QoSProfile(depth=10),
        blackboard_variables={"battery_msg": ""},   # "" = whole message
        clearing_policy=py_trees.common.ClearingPolicy.NEVER
    )

    battery_monitor = BatteryMonitor()

    # --- BRANCH 2: 4-LEVEL PRIORITIES ---
    # Memory must be false so higher priority branches can preempt lower priority ones continuously
    priorities = py_trees.composites.Selector(name="Priorities", memory=False)
    
    survival_l1 = create_survival_subtree()
    preemption_l2 = create_preemption_subtree()
    mission_l3_raw = create_mission_subtree()
    mission_l3_tracked = MissionStatusTracker(
        child=mission_l3_raw,
        name="MissionStatusTracker",
        default_mission_type="social_approach",
    )

    # BTA-050/BTA-051:
    # L3 runs through an explicit admission contract (formal objective,
    # battery policy and cooldown) while mission execution remains isolated in
    # mission_tree.py.
    mission_l3 = py_trees.composites.Sequence(name="L3_AdmissionAndExecution", memory=False)
    mission_l3.add_children([
        MissionAdmissionGate(name="MissionAdmissionGate"),
        mission_l3_tracked,
    ])
    idle_l4 = create_idle_subtree()

    # -- Build Tree ---
    root.add_children([topics2bb, priorities])
    topics2bb.add_children([doa2bb, hotword2bb, odom_yaw2bb, speaker2bb, waypoint2bb, battery2bb, battery_monitor])
    priorities.add_children([survival_l1, preemption_l2, mission_l3, idle_l4])
    
    return root

def main():
    rclpy.init()

    # -- Global Configuration ---
    config_bb = py_trees.blackboard.Client(name="GlobalConfig")

    # Register BB variables
    config_bb.register_key(key="config/max_head_angle", access=py_trees.common.Access.WRITE)
    config_bb.register_key(key="config/far_angle_limit", access=py_trees.common.Access.WRITE)
    # BTA-010: dock_pose — default is the map origin facing forward (+X direction).
    # Override this key at runtime (e.g. from a parameter server node) to point
    # the robot at the actual docking station.
    config_bb.register_key(key="config/dock_pose", access=py_trees.common.Access.WRITE)

    # Set config values
    config_bb.set("config/max_head_angle", 90.0)
    config_bb.set("config/far_angle_limit", 60.0)

    # Default dock pose: map origin (0, 0) facing forward (quaternion w=1)
    _dock_pose = PoseStamped()
    _dock_pose.header.frame_id = "map"
    _dock_pose.pose.position.x = 0.0
    _dock_pose.pose.position.y = 0.0
    _dock_pose.pose.position.z = 0.0
    _dock_pose.pose.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    config_bb.set("config/dock_pose", _dock_pose)

    # BTA-001: Arbitration state — global keys used by all layers for priority arbitration.
    # Initialised here with safe defaults so every subtree can read them from tick 0
    # without raising KeyError.
    arbitration_bb = py_trees.blackboard.Client(name="ArbitrationState")
    arbitration_bb.register_key(key="mission/active",     access=py_trees.common.Access.WRITE)
    arbitration_bb.register_key(key="mission/type",       access=py_trees.common.Access.WRITE)
    arbitration_bb.register_key(key="mission/id",         access=py_trees.common.Access.WRITE)
    arbitration_bb.register_key(key="mission/cooldown_sec", access=py_trees.common.Access.WRITE)
    arbitration_bb.register_key(key="mission/cooldown_until", access=py_trees.common.Access.WRITE)
    arbitration_bb.register_key(key="mission/last_outcome", access=py_trees.common.Access.WRITE)
    arbitration_bb.register_key(key="preemption/active",  access=py_trees.common.Access.WRITE)
    arbitration_bb.set("mission/active",    False)
    arbitration_bb.set("mission/type",      "")
    arbitration_bb.set("mission/id",        "")
    arbitration_bb.set("mission/cooldown_sec", 6.0)
    arbitration_bb.set("mission/cooldown_until", 0.0)
    arbitration_bb.set("mission/last_outcome", "none")
    arbitration_bb.set("preemption/active", False)

    # BTA-002: Observability keys — written by LayerReporter on each tick.
    observability_bb = py_trees.blackboard.Client(name="Observability")
    observability_bb.register_key(key="active_layer",  access=py_trees.common.Access.WRITE)
    observability_bb.register_key(key="active_reason", access=py_trees.common.Access.WRITE)
    observability_bb.set("active_layer",  "none")
    observability_bb.set("active_reason", "initialising")

    # --- Tree Creation ---
    root = create_root()
    tree = py_trees_ros.trees.BehaviourTree(
        root=root, 
        unicode_tree_debug=True
    )
    
    # Visualization: Render a static DOT/PNG graph of the tree structure.
    import os
    try:
        py_trees.display.render_dot_tree(root, target_directory=os.getcwd())
        print(f"\\n--- Static Tree rendered to {os.getcwd()} ---")
    except Exception as e:
        print(f"\\n--- Could not render static tree: {e} ---")

    tree.visitors.append(py_trees.visitors.DisplaySnapshotVisitor(display_blackboard=True))

    try:
        tree.setup(timeout=15.0)
        print("\\n--- Main Behavior Tree Initialized Successfully ---")
        tree.tick_tock(period_ms=100)
        rclpy.spin(tree.node)
    except (KeyboardInterrupt, py_trees_ros.exceptions.NotReadyError):
        print("\\nStopping behavior tree execution...")
    finally:
        tree.shutdown()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()