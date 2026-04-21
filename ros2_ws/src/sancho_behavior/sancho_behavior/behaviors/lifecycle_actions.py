import py_trees
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState, GetState

class LifecycleTransition(py_trees.behaviour.Behaviour):
    """
    Triggers a lifecycle transition for a given node.
    """
    def __init__(self, name, node_name, transition_id):
        super().__init__(name)
        self.node_name = node_name
        self.transition_id = transition_id

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.cli = self.node.create_client(ChangeState, f"/{self.node_name}/change_state")
        self.future = None

    def initialise(self):
        self.node.get_logger().info(f"{self.name}: Requesting transition {self.transition_id} for {self.node_name}")
        if not self.cli.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().error(f"{self.name}: Service /{self.node_name}/change_state not available")
            self.status = py_trees.common.Status.FAILURE
            return

        req = ChangeState.Request()
        req.transition.id = self.transition_id
        self.future = self.cli.call_async(req)

    def update(self):
        if self.future is None:
            return py_trees.common.Status.FAILURE

        if self.future.done():
            result = self.future.result()
            if result and result.success:
                self.node.get_logger().info(f"{self.name}: Transition successful")
                return py_trees.common.Status.SUCCESS
            else:
                self.node.get_logger().error(f"{self.name}: Transition failed")
                return py_trees.common.Status.FAILURE

        return py_trees.common.Status.RUNNING


class ActivateNode(LifecycleTransition):
    def __init__(self, name="ActivateNode", node_name="node"):
        super().__init__(name, node_name, Transition.TRANSITION_ACTIVATE)

class DeactivateNode(LifecycleTransition):
    def __init__(self, name="DeactivateNode", node_name="node"):
        super().__init__(name, node_name, Transition.TRANSITION_DEACTIVATE)
