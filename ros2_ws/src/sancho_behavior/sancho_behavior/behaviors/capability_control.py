import py_trees
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger


class CapabilitySetMode(py_trees.behaviour.Behaviour):
    """Best-effort mode publication for shared capabilities."""

    def __init__(self, mode: str, topic: str, name: str = "CapabilitySetMode"):
        super().__init__(name)
        self.mode = mode
        self.topic = topic
        self.publisher = None

    def setup(self, **kwargs):
        node = kwargs["node"]
        self.publisher = node.create_publisher(String, self.topic, 10)

    def update(self) -> py_trees.common.Status:
        if self.publisher is None:
            return py_trees.common.Status.SUCCESS
        msg = String()
        msg.data = self.mode
        self.publisher.publish(msg)
        return py_trees.common.Status.SUCCESS


class CapabilityEnable(py_trees.behaviour.Behaviour):
    """Best-effort capability enable handshake through SetBool."""

    def __init__(self, service_name: str, name: str = "CapabilityEnable"):
        super().__init__(name)
        self.service_name = service_name
        self.client = None
        self.future = None

    def setup(self, **kwargs):
        node = kwargs["node"]
        self.client = node.create_client(SetBool, self.service_name)

    def initialise(self):
        self.future = None

    def update(self) -> py_trees.common.Status:
        if self.client is None:
            return py_trees.common.Status.SUCCESS

        if self.future is None:
            if not self.client.wait_for_service(timeout_sec=0.05):
                return py_trees.common.Status.SUCCESS
            req = SetBool.Request()
            req.data = True
            self.future = self.client.call_async(req)
            return py_trees.common.Status.RUNNING

        if not self.future.done():
            return py_trees.common.Status.RUNNING

        result = self.future.result()
        return py_trees.common.Status.SUCCESS if result is not None and result.success else py_trees.common.Status.FAILURE


class CapabilityDisable(py_trees.behaviour.Behaviour):
    """Best-effort capability disable handshake through Trigger."""

    def __init__(self, service_name: str, name: str = "CapabilityDisable"):
        super().__init__(name)
        self.service_name = service_name
        self.client = None
        self.future = None

    def setup(self, **kwargs):
        node = kwargs["node"]
        self.client = node.create_client(Trigger, self.service_name)

    def initialise(self):
        self.future = None

    def update(self) -> py_trees.common.Status:
        if self.client is None:
            return py_trees.common.Status.SUCCESS

        if self.future is None:
            if not self.client.wait_for_service(timeout_sec=0.05):
                return py_trees.common.Status.SUCCESS
            req = Trigger.Request()
            self.future = self.client.call_async(req)
            return py_trees.common.Status.RUNNING

        if not self.future.done():
            return py_trees.common.Status.RUNNING

        result = self.future.result()
        return py_trees.common.Status.SUCCESS if result is not None and result.success else py_trees.common.Status.FAILURE
