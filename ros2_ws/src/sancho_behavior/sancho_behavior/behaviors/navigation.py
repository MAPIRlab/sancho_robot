import py_trees
import py_trees_ros
from py_trees.blackboard import Client
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from nav2_msgs.srv import ManageLifecycleNodes

class NavigateToGroupPose(py_trees_ros.action_clients.FromBlackboard):
    """
    Sends a navigation goal to Nav2 using a target pose from the blackboard.
    """
    def __init__(self, name="NavigateToGroupPose", action_name="navigate_to_pose"):
        super().__init__(
            name=name,
            action_type=NavigateToPose,
            action_name=action_name,
            key="navigate_goal",
            wait_for_server_timeout_sec=0.0
        )
        self.blackboard = Client(name=self.name)
        self.blackboard.register_key("group_waypoint_pose", access=py_trees.common.Access.READ)
        self.blackboard.register_key("navigate_goal", access=py_trees.common.Access.WRITE)

    def initialise(self):
        pose = self.blackboard.group_waypoint_pose if self.blackboard.exists("group_waypoint_pose") else None
        
        if pose is None:
            self.node.get_logger().error(f"{self.name}: No pose on blackboard!")
            self.blackboard.navigate_goal = None
            return super().initialise()

        goal = NavigateToPose.Goal()
        goal.pose = pose
        self.blackboard.navigate_goal = goal
        return super().initialise()

class ManageNav2Lifecycle(py_trees.behaviour.Behaviour):
    """
    Calls /lifecycle_manager_navigation/manage_nodes to PAUSE (1) or RESUME (2) Nav2.
    """
    def __init__(self, name="ManageNav2", command=1):
        super().__init__(name)
        self.command = command # 1 = PAUSE, 2 = RESUME

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.cli = self.node.create_client(ManageLifecycleNodes, '/lifecycle_manager_navigation/manage_nodes')
        self.future = None

    def initialise(self):
        if not self.cli.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().error(f"{self.name}: Nav2 manage_nodes service not available")
            self.status = py_trees.common.Status.FAILURE
            return

        req = ManageLifecycleNodes.Request()
        req.command = self.command
        self.future = self.cli.call_async(req)

    def update(self):
        if self.future is None:
            return py_trees.common.Status.FAILURE

        if self.future.done():
            result = self.future.result()
            if result and result.success:
                return py_trees.common.Status.SUCCESS
            return py_trees.common.Status.FAILURE

        return py_trees.common.Status.RUNNING

class PauseNavigation(ManageNav2Lifecycle):
    def __init__(self, name="PauseNavigation"):
        super().__init__(name, command=1)

class ResumeNavigation(ManageNav2Lifecycle):
    def __init__(self, name="ResumeNavigation"):
        super().__init__(name, command=2)


class NavigateToDock(py_trees_ros.action_clients.FromBlackboard):
    """
    BTA-010: Sends a NavigateToPose goal to Nav2 using the dock pose stored
    on the blackboard (``config/dock_pose``).

    Blackboard Reads:
        config/dock_pose (PoseStamped): Target docking pose. Initialised in
            main() with a safe default (origin, facing forward). Can be
            overridden via a parameter or a separate configuration node.

    Action:
        navigate_to_pose (nav2_msgs/action/NavigateToPose)

    Returns:
        SUCCESS — Nav2 reached the dock pose.
        FAILURE — Nav2 rejected or failed the goal, or pose is missing.
        RUNNING — Nav2 is still navigating.

    Usage (survival_tree.py):
        Wrap in py_trees.decorators.Timeout(duration=120.0) so that a
        stuck robot does not hold L1 indefinitely.
    """

    def __init__(self, name: str = "NavigateToDock", action_name: str = "navigate_to_pose"):
        super().__init__(
            name=name,
            action_type=NavigateToPose,
            action_name=action_name,
            key="dock_nav_goal",          # internal BB key for the goal msg
            wait_for_server_timeout_sec=0.0
        )
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key("config/dock_pose",  access=py_trees.common.Access.READ)
        self.bb.register_key("dock_nav_goal",     access=py_trees.common.Access.WRITE)

    def initialise(self):
        """Build the NavigateToPose.Goal from config/dock_pose and write it
        to the blackboard so FromBlackboard can pick it up."""
        try:
            dock_pose: PoseStamped = self.bb.get("config/dock_pose")
        except KeyError:
            self.logger.error(
                f"{self.name}: 'config/dock_pose' not found on blackboard — "
                "cannot send docking goal. Did main() initialise GlobalConfig?"
            )
            self.bb.dock_nav_goal = None
            return super().initialise()

        goal = NavigateToPose.Goal()
        goal.pose = dock_pose
        self.bb.dock_nav_goal = goal
        self.logger.info(
            f"{self.name}: Sending dock goal to "
            f"({dock_pose.pose.position.x:.2f}, {dock_pose.pose.position.y:.2f})"
        )
        return super().initialise()
