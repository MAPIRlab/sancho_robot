import py_trees

from sancho_interfaces.srv import EndInteraction


class EnsureAttentionManagerReady(py_trees.behaviour.Behaviour):
    """
    Verifies that the attention manager endpoint is available before
    considering L2 preemption handling complete.

    This is used as a real handshake to replace the former L2 stub.
    """

    def __init__(
        self,
        name: str = "EnsureAttentionManagerReady",
        service_name: str = "/attention_manager/interaction_finished",
        timeout_sec: float = 0.3,
    ):
        super().__init__(name)
        self.service_name = service_name
        self.timeout_sec = timeout_sec
        self.node = None
        self.cli = None
        self._last_available = None

    def setup(self, **kwargs):
        self.node = kwargs["node"]
        self.cli = self.node.create_client(EndInteraction, self.service_name)

    def update(self) -> py_trees.common.Status:
        if self.cli is None:
            return py_trees.common.Status.FAILURE

        available = self.cli.wait_for_service(timeout_sec=self.timeout_sec)

        if available != self._last_available:
            if available:
                self.node.get_logger().info(
                    f"{self.name}: handshake OK ({self.service_name})"
                )
            else:
                self.node.get_logger().warn(
                    f"{self.name}: endpoint not available ({self.service_name})"
                )
            self._last_available = available

        if available:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE
