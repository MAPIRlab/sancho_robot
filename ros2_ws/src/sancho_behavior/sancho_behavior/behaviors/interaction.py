import py_trees
import py_trees_ros
from py_trees.blackboard import Client
from sancho_interfaces.srv import GreetPeople, GetCentralFaceCluster
from sancho_interfaces.srv import SocialState

class GreetUser(py_trees.behaviour.Behaviour):
    """
    Calls the GreetPeople service with user names from the blackboard.
    """
    def __init__(self, name="GreetUser"):
        super().__init__(name)
        self.blackboard = Client(name=self.name)
        self.blackboard.register_key("target_names", access=py_trees.common.Access.READ)
        self.blackboard.register_key("target_ids", access=py_trees.common.Access.READ)
        
    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.cli = self.node.create_client(GreetPeople, 'assistant/greet_people')
        self.future = None

    def initialise(self):
        if not self.cli.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().error(f"{self.name}: Service assistant/greet_people not available")
            self.status = py_trees.common.Status.FAILURE
            return
            
        req = GreetPeople.Request()
        req.names = self.blackboard.target_names if self.blackboard.exists("target_names") else []
        req.ids = self.blackboard.target_ids if self.blackboard.exists("target_ids") else []
        
        self.future = self.cli.call_async(req)

    def update(self):
        if self.future is None:
            return py_trees.common.Status.FAILURE
            
        if self.future.done():
            result = self.future.result()
            if result and result.accepted:
                return py_trees.common.Status.SUCCESS
            return py_trees.common.Status.FAILURE
            
        return py_trees.common.Status.RUNNING

class IdentifyCentralTarget(py_trees.behaviour.Behaviour):
    """
    Calls the GetCentralFaceCluster service and writes the central target to the blackboard.
    """
    def __init__(self, name="IdentifyCentralTarget"):
        super().__init__(name)
        self.blackboard = Client(name=self.name)
        self.blackboard.register_key("target_names", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("target_ids", access=py_trees.common.Access.WRITE)
        
    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.cli = self.node.create_client(GetCentralFaceCluster, '/central_faces_cluster_node/get_central_cluster')
        self.future = None

    def initialise(self):
        if not self.cli.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().error(f"{self.name}: Service /central_faces_cluster_node/get_central_cluster not available")
            self.status = py_trees.common.Status.FAILURE
            return
            
        req = GetCentralFaceCluster.Request()
        self.future = self.cli.call_async(req)

    def update(self):
        if self.future is None:
            return py_trees.common.Status.FAILURE
            
        if self.future.done():
            result = self.future.result()
            if result:
                self.blackboard.target_names = list(result.names)
                self.blackboard.target_ids = list(result.ids)
                return py_trees.common.Status.SUCCESS
            return py_trees.common.Status.FAILURE
            
        return py_trees.common.Status.RUNNING

class WaitForSocialInteraction(py_trees.behaviour.Behaviour):
    """
    Hosts the /social_state service and waits for the interaction manager to report it is finished.
    """
    def __init__(self, name="WaitForSocialInteraction", timeout_sec=60.0):
        super().__init__(name)
        self.timeout_sec = timeout_sec
        self.SocialStateClass = SocialState
        # constants
        self.STATE_READY = 0
        self.STATE_FINISHED = 1
        self.STATE_ERROR = 2
        self.state = self.STATE_READY

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.srv = self.node.create_service(
            self.SocialStateClass, "/social_state", self._svc_callback
        )
        self.state = self.STATE_READY
        self.start_time = None

    def _svc_callback(self, request, response):
        self.state = request.state
        return response

    def initialise(self):
        self.state = self.STATE_READY
        self.start_time = self.node.get_clock().now()

    def update(self):
        if self.state == self.STATE_FINISHED:
            return py_trees.common.Status.SUCCESS
        elif self.state == self.STATE_ERROR:
            return py_trees.common.Status.FAILURE
            
        elapsed = (self.node.get_clock().now() - self.start_time).nanoseconds / 1e9
        if elapsed > self.timeout_sec:
            self.node.get_logger().warn(f"{self.name}: Timeout exceeded")
            return py_trees.common.Status.FAILURE
            
        return py_trees.common.Status.RUNNING
