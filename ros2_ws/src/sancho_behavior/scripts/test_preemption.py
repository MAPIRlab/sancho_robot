import py_trees
from sancho_behavior.trees.main_tree import create_root

def test_scenario():
    print("=========================================================")
    print("BTA-082: Preemption and Resume Regression Tests")
    print("=========================================================")

    # 1. Setup Tree
    import rclpy
    import py_trees_ros
    
    # Mock ROS setups to prevent hanging on missing action servers
    py_trees_ros.action_clients.FromBlackboard.setup = lambda self, **kwargs: None
    py_trees_ros.action_clients.FromConstant.setup = lambda self, **kwargs: None
    py_trees_ros.service_clients.FromConstant.setup = lambda self, **kwargs: None
    py_trees_ros.service_clients.FromCallback.setup = lambda self, **kwargs: None
    
    # Mock lifecycle actions
    import sancho_behavior.behaviors.lifecycle_actions
    sancho_behavior.behaviors.lifecycle_actions.ActivateNode.update = lambda self: py_trees.common.Status.SUCCESS
    sancho_behavior.behaviors.lifecycle_actions.DeactivateNode.update = lambda self: py_trees.common.Status.SUCCESS
    sancho_behavior.behaviors.lifecycle_actions.ActivateNode.setup = lambda self, **kwargs: None
    sancho_behavior.behaviors.lifecycle_actions.DeactivateNode.setup = lambda self, **kwargs: None
    sancho_behavior.behaviors.lifecycle_actions.ActivateNode.initialise = lambda self: None
    sancho_behavior.behaviors.lifecycle_actions.DeactivateNode.initialise = lambda self: None
    
    import sancho_behavior.behaviors.navigation
    sancho_behavior.behaviors.navigation.NavigateToGroupPose.initialise = lambda self: None
    sancho_behavior.behaviors.navigation.NavigateToGroupPose.update = lambda self: py_trees.common.Status.RUNNING
    sancho_behavior.behaviors.navigation.NavigateToGroupPose.stop = lambda self, new_status: None
    sancho_behavior.behaviors.navigation.PauseNavigation.initialise = lambda self: None
    sancho_behavior.behaviors.navigation.PauseNavigation.update = lambda self: py_trees.common.Status.SUCCESS
    sancho_behavior.behaviors.navigation.PauseNavigation.stop = lambda self, new_status: None
    sancho_behavior.behaviors.navigation.ResumeNavigation.initialise = lambda self: None
    sancho_behavior.behaviors.navigation.ResumeNavigation.update = lambda self: py_trees.common.Status.SUCCESS
    sancho_behavior.behaviors.navigation.ResumeNavigation.stop = lambda self, new_status: None
    sancho_behavior.behaviors.navigation.NavigateToDock.initialise = lambda self: None
    sancho_behavior.behaviors.navigation.NavigateToDock.update = lambda self: py_trees.common.Status.RUNNING
    sancho_behavior.behaviors.navigation.NavigateToDock.stop = lambda self, new_status: None
    
    import sancho_behavior.behaviors.preemption_checks
    sancho_behavior.behaviors.preemption_checks.EnsureAttentionManagerReady.initialise = lambda self: None
    sancho_behavior.behaviors.preemption_checks.EnsureAttentionManagerReady.update = lambda self: py_trees.common.Status.SUCCESS
    
    import sancho_behavior.behaviors.proxy_subtree
    sancho_behavior.behaviors.proxy_subtree.ProxySubtreeBehavior.update = lambda self: py_trees.common.Status.SUCCESS
    
    import sancho_behavior.behaviors.battery_monitor
    sancho_behavior.behaviors.battery_monitor.BatteryMonitor.update = lambda self: py_trees.common.Status.SUCCESS
    
    # Disable ToBlackboard overwriting our mock variables
    py_trees_ros.subscribers.ToBlackboard.update = lambda self: py_trees.common.Status.SUCCESS
    py_trees_ros.subscribers.EventToBlackboard.update = lambda self: py_trees.common.Status.SUCCESS
    
    # Import subtrees to populate registry
    import sancho_behavior.trees.react_to_sound_tree
    import sancho_behavior.trees.interaction_tree
    
    node = rclpy.create_node("test_preemption_node")
    root = create_root()
    tree = py_trees_ros.trees.BehaviourTree(root)
    tree.setup(node=node)
    
    # We use a custom blackboard client
    bb = py_trees.blackboard.Client(name="TestClient")
    bb.register_key("battery_critical", access=py_trees.common.Access.WRITE)
    bb.register_key("hotword_event", access=py_trees.common.Access.WRITE)
    bb.register_key("group_waypoint_pose", access=py_trees.common.Access.WRITE)
    bb.register_key("mission/active", access=py_trees.common.Access.WRITE)
    bb.register_key("/battery_msg", access=py_trees.common.Access.WRITE)
    bb.register_key("battery_degraded", access=py_trees.common.Access.WRITE)
    
    # Initialize variables
    bb.battery_critical = False
    bb.hotword_event = False
    bb.battery_degraded = False
    
    from sensor_msgs.msg import BatteryState
    msg = BatteryState()
    msg.percentage = 1.0
    msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            
    bb.set("/battery_msg", msg)
    
    # Tick 1: Idle
    print("\n--- TICK 1: IDLE ---")
    root.tick_once()
    print(py_trees.display.unicode_tree(root, show_status=True))

    # Tick 2: Trigger Mission L3
    print("\n--- TICK 2: TRIGGER MISSION L3 ---")
    from geometry_msgs.msg import PoseStamped
    dummy_pose = PoseStamped()
    dummy_pose.header.frame_id = "map"
    bb.set("group_waypoint_pose", dummy_pose)
    bb.set("mission/active", True)
    root.tick_once()
    print(py_trees.display.unicode_tree(root, show_status=True))

    # Tick 3: L3 Running, trigger L2 (Preemption)
    print("\n--- TICK 3: L2 PREEMPTS L3 ---")
    bb.set("hotword_event", True)
    root.tick_once()
    print(py_trees.display.unicode_tree(root, show_status=True))
    
    # Tick 4: L2 clears hotword and finishes
    print("\n--- TICK 4: L2 FINISHES (Resume L3) ---")
    bb.set("hotword_event", False)
    root.tick_once()
    print(py_trees.display.unicode_tree(root, show_status=True))

    # Tick 5: L3 resumes normally
    print("\n--- TICK 5: L3 RESUMES ---")
    root.tick_once()
    print(py_trees.display.unicode_tree(root, show_status=True))

    # Tick 6: L1 triggers (Critical Battery)
    print("\n--- TICK 6: L1 PREEMPTS L3 ---")
    bb.set("battery_critical", True)
    root.tick_once()
    print(py_trees.display.unicode_tree(root, show_status=True))

    print("\n=========================================================")
    print("Tests completed. Check logs for Preemptable behaviors.")
    print("=========================================================")

if __name__ == "__main__":
    import logging
    py_trees.logging.level = py_trees.logging.Level.INFO
    logging.basicConfig(level=logging.INFO)
    
    # Provide dummy implementations for ROS nodes if needed, or just let them fail
    # Since these are py_trees ROS behaviors, they might need rclpy.init()
    import rclpy
    rclpy.init()
    try:
        test_scenario()
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        rclpy.shutdown()
