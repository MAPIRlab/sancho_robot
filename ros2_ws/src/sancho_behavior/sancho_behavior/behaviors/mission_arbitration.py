import py_trees
import py_trees.decorators


class MissionAdmissionGate(py_trees.behaviour.Behaviour):
    """
    BTA-050: Admission contract between L3 (missions) and L4 (idle).

    Rules:
    - If mission/active=True: allow mission execution to continue.
    - Else, only admit L3 when:
      1) a formal objective exists (group_waypoint_pose on BB),
      2) battery is not degraded,
      3) cooldown after last mission exit has expired.
    """

    def __init__(self, name: str = "MissionAdmissionGate"):
        super().__init__(name)
        self.node = None
        self.bb = self.attach_blackboard_client(name=self.name)

        self.bb.register_key(key="mission/active", access=py_trees.common.Access.READ)
        self.bb.register_key(key="mission/cooldown_until", access=py_trees.common.Access.READ)
        self.bb.register_key(key="battery_degraded", access=py_trees.common.Access.READ)
        self.bb.register_key(key="mission/request", access=py_trees.common.Access.READ)

    def setup(self, **kwargs):
        self.node = kwargs["node"]

    def _now_sec(self) -> float:
        if self.node is None:
            return 0.0
        return self.node.get_clock().now().nanoseconds / 1e9

    def update(self) -> py_trees.common.Status:
        mission_active = self.bb.get("mission/active") if self.bb.exists("mission/active") else False
        if mission_active:
            return py_trees.common.Status.SUCCESS

        mission_request = self.bb.get("mission/request") if self.bb.exists("mission/request") else None
        if not mission_request:
            return py_trees.common.Status.FAILURE

        battery_degraded = self.bb.get("battery_degraded") if self.bb.exists("battery_degraded") else False
        if battery_degraded:
            return py_trees.common.Status.FAILURE

        cooldown_until = self.bb.get("mission/cooldown_until") if self.bb.exists("mission/cooldown_until") else 0.0
        if self._now_sec() < cooldown_until:
            return py_trees.common.Status.FAILURE

        return py_trees.common.Status.SUCCESS


class MissionStatusTracker(py_trees.decorators.Decorator):
    """
    BTA-051: Tracks mission lifecycle and applies a cooldown latch on exit.

    This decorator wraps the L3 mission subtree and updates mission metadata
    in the blackboard without coupling mission internals to arbitration policy.
    """

    def __init__(
        self,
        child: py_trees.behaviour.Behaviour,
        name: str = "MissionStatusTracker",
    ):
        super().__init__(name=name, child=child)
        self.node = None
        self.bb = self.attach_blackboard_client(name=self.name)

        self.bb.register_key(key="mission/active", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/type", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/request", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/id", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/cooldown_sec", access=py_trees.common.Access.READ)
        self.bb.register_key(key="mission/cooldown_until", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/last_outcome", access=py_trees.common.Access.WRITE)

    def setup(self, **kwargs):
        self.node = kwargs["node"]

    def _now_sec(self) -> float:
        if self.node is None:
            return 0.0
        return self.node.get_clock().now().nanoseconds / 1e9

    def _ensure_mission_context(self):
        now_sec = self._now_sec()
        mission_request = self.bb.get("mission/request") if self.bb.exists("mission/request") else None
        if mission_request:
            self.bb.set("mission/type", mission_request)

        mission_id = self.bb.get("mission/id") if self.bb.exists("mission/id") else ""
        if not mission_id:
            self.bb.set("mission/id", f"m-{int(now_sec * 1000)}")

    def initialise(self) -> None:
        mission_active = self.bb.get("mission/active") if self.bb.exists("mission/active") else False
        if not mission_active:
            self._ensure_mission_context()
            self.bb.set("mission/active", True)

    def update(self) -> py_trees.common.Status:
        status = self.decorated.status

        mission_active = self.bb.get("mission/active") if self.bb.exists("mission/active") else False

        if status in (py_trees.common.Status.SUCCESS, py_trees.common.Status.FAILURE):
            if mission_active:
                cooldown_sec = self.bb.get("mission/cooldown_sec") if self.bb.exists("mission/cooldown_sec") else 6.0
                self.bb.set("mission/active", False)
                self.bb.set("mission/last_outcome", status.name.lower())
                self.bb.set("mission/cooldown_until", self._now_sec() + float(cooldown_sec))

                # Reset mission identity so the next admission creates a new mission id.
                self.bb.set("mission/id", "")
                self.bb.set("mission/type", "")
                self.bb.set("mission/request", None)

        return status
