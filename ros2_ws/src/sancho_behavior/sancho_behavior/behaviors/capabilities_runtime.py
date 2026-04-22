import py_trees
from std_msgs.msg import String
from std_srvs.srv import SetBool, Trigger


class ActiveLayerResourceRequests(py_trees.behaviour.Behaviour):
    """Populate layer resource requests from active_layer for deterministic arbitration."""

    LAYERS = ("L1", "L2", "L3", "L4")
    RESOURCES = ("head", "base", "face")

    # Conservative defaults: higher layers can request all resources.
    LAYER_RESOURCE_MAP = {
        "L1": {"head", "base", "face"},
        "L2": {"head", "base", "face"},
        "L3": {"head", "base", "face"},
        "L4": {"head"},
    }

    def __init__(self, name: str = "ActiveLayerResourceRequests"):
        super().__init__(name)
        self.bb = self.attach_blackboard_client(name=self.name)
        self.bb.register_key(key="active_layer", access=py_trees.common.Access.READ)
        for layer in self.LAYERS:
            for resource in self.RESOURCES:
                self.bb.register_key(
                    key=f"resource/{resource}/requester/{layer}",
                    access=py_trees.common.Access.WRITE,
                )

    def update(self) -> py_trees.common.Status:
        active_layer = self.bb.get("active_layer") if self.bb.exists("active_layer") else "none"
        allowed = self.LAYER_RESOURCE_MAP.get(str(active_layer), set())

        for layer in self.LAYERS:
            for resource in self.RESOURCES:
                self.bb.set(
                    f"resource/{resource}/requester/{layer}",
                    layer == active_layer and resource in allowed,
                )

        return py_trees.common.Status.SUCCESS


class ResourceArbiter(py_trees.behaviour.Behaviour):
    """Assigns a single owner per resource according to strict priority order."""

    REQUESTERS = ("L1", "L2", "L3", "L4", "capability_tracking")
    RESOURCES = ("head", "base", "face")

    def __init__(self, name: str = "ResourceArbiter"):
        super().__init__(name)
        self.bb = self.attach_blackboard_client(name=self.name)

        for resource in self.RESOURCES:
            self.bb.register_key(key=f"resource/{resource}/owner", access=py_trees.common.Access.WRITE)
            self.bb.register_key(key=f"resource/{resource}/locked", access=py_trees.common.Access.WRITE)
            for requester in self.REQUESTERS:
                self.bb.register_key(
                    key=f"resource/{resource}/requester/{requester}",
                    access=py_trees.common.Access.READ,
                )

    def update(self) -> py_trees.common.Status:
        for resource in self.RESOURCES:
            owner = ""
            for requester in self.REQUESTERS:
                key = f"resource/{resource}/requester/{requester}"
                requested = self.bb.get(key) if self.bb.exists(key) else False
                if requested:
                    owner = requester
                    break

            self.bb.set(f"resource/{resource}/owner", owner)
            self.bb.set(f"resource/{resource}/locked", bool(owner))

        return py_trees.common.Status.SUCCESS


class ManageTrackingCapability(py_trees.behaviour.Behaviour):
    """
    Runtime tracking capability with TTL and best-effort service handshake.

    This behavior never commands actuators directly; it only manages capability
    state and intent so it can safely run in a persistent parallel branch.
    """

    def __init__(
        self,
        name: str = "ManageTrackingCapability",
        enable_service: str = "/attention_manager/capability/tracking/enable",
        disable_service: str = "/attention_manager/capability/tracking/disable",
        mode_topic: str = "/attention_manager/capability/tracking/set_mode",
    ):
        super().__init__(name)
        self.enable_service = enable_service
        self.disable_service = disable_service
        self.mode_topic = mode_topic

        self.node = None
        self.enable_client = None
        self.disable_client = None
        self.mode_pub = None

        self.enable_future = None
        self.disable_future = None
        self.mode_sent = ""

        self.bb = self.attach_blackboard_client(name=self.name)
        for key in (
            "mission/active",
            "hotword_event",
            "is_engaged",
            "config/capability_tracking_ttl_sec",
            "resource/head/owner",
            "capability/tracking/enabled",
            "capability/tracking/mode",
            "capability/tracking/active_until",
            "resource/head/requester/capability_tracking",
        ):
            access = py_trees.common.Access.READ
            if key.startswith("capability/") or key.startswith("resource/head/requester"):
                access = py_trees.common.Access.WRITE
            self.bb.register_key(key=key, access=access)

    def setup(self, **kwargs):
        self.node = kwargs["node"]
        self.enable_client = self.node.create_client(SetBool, self.enable_service)
        self.disable_client = self.node.create_client(Trigger, self.disable_service)
        self.mode_pub = self.node.create_publisher(String, self.mode_topic, 10)

    def _now_sec(self) -> float:
        return self.node.get_clock().now().nanoseconds / 1e9 if self.node else 0.0

    def _call_enable(self):
        if self.enable_future is not None:
            return
        if not self.enable_client.wait_for_service(timeout_sec=0.05):
            return
        req = SetBool.Request()
        req.data = True
        self.enable_future = self.enable_client.call_async(req)

    def _call_disable(self):
        if self.disable_future is not None:
            return
        if not self.disable_client.wait_for_service(timeout_sec=0.05):
            return
        req = Trigger.Request()
        self.disable_future = self.disable_client.call_async(req)

    def _publish_mode(self, mode: str):
        if self.mode_pub is None or self.mode_sent == mode:
            return
        msg = String()
        msg.data = mode
        self.mode_pub.publish(msg)
        self.mode_sent = mode

    def _handle_futures(self):
        if self.enable_future is not None and self.enable_future.done():
            result = self.enable_future.result()
            if result is not None and result.success:
                self.bb.set("capability/tracking/enabled", True)
            self.enable_future = None

        if self.disable_future is not None and self.disable_future.done():
            result = self.disable_future.result()
            if result is not None and result.success:
                self.bb.set("capability/tracking/enabled", False)
            self.disable_future = None

    def update(self) -> py_trees.common.Status:
        self._handle_futures()

        now = self._now_sec()
        ttl = (
            float(self.bb.get("config/capability_tracking_ttl_sec"))
            if self.bb.exists("config/capability_tracking_ttl_sec")
            else 20.0
        )

        mission_active = self.bb.get("mission/active") if self.bb.exists("mission/active") else False
        hotword_event = self.bb.get("hotword_event") if self.bb.exists("hotword_event") else False
        is_engaged = self.bb.get("is_engaged") if self.bb.exists("is_engaged") else False

        active_until = (
            float(self.bb.get("capability/tracking/active_until"))
            if self.bb.exists("capability/tracking/active_until")
            else 0.0
        )

        if mission_active or hotword_event or is_engaged:
            active_until = max(active_until, now + ttl)
            self.bb.set("capability/tracking/mode", "active")

        head_owner = self.bb.get("resource/head/owner") if self.bb.exists("resource/head/owner") else ""
        can_request = head_owner in ("", "capability_tracking")
        should_enable = can_request and now < active_until

        self.bb.set("resource/head/requester/capability_tracking", should_enable)
        self.bb.set("capability/tracking/active_until", active_until)

        enabled = self.bb.get("capability/tracking/enabled") if self.bb.exists("capability/tracking/enabled") else False

        if should_enable and not enabled:
            self._publish_mode("active")
            self._call_enable()
        elif not should_enable and enabled:
            self.bb.set("capability/tracking/mode", "standby")
            self._publish_mode("standby")
            self._call_disable()

        return py_trees.common.Status.RUNNING
