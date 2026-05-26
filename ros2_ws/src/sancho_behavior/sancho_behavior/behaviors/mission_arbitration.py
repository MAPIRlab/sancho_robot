import py_trees
import py_trees.decorators


class MissionAdmissionGate(py_trees.behaviour.Behaviour):
    """
    BTA-050: Admission contract between L3 (missions) and L4 (idle).

    Decides whether the mission subtree is allowed to tick.

    Rules (in order):
      1. If mission/active=True  → ya hay una misión en curso, dejar pasar (SUCCESS).
      2. If mission/request is None or "idle"  → no hay misión pendiente (FAILURE).
      3. If battery_degraded=True  → no admitir nuevas misiones (FAILURE).
      4. Otherwise  → admitir (SUCCESS).

    This behaviour is READ-ONLY: it never writes to the blackboard.
    All write authority over mission/active, mission/request, mission/type
    belongs exclusively to MissionActionServer.
    """

    def __init__(self, name: str = "MissionAdmissionGate"):
        super().__init__(name)
        self.node = None
        self.bb = self.attach_blackboard_client(name=self.name)

        # READ-ONLY keys
        self.bb.register_key(key="mission/active",    access=py_trees.common.Access.READ)
        self.bb.register_key(key="mission/request",   access=py_trees.common.Access.READ)
        self.bb.register_key(key="battery_degraded",  access=py_trees.common.Access.READ)

    def setup(self, **kwargs):
        self.node = kwargs["node"]

    def update(self) -> py_trees.common.Status:
        # ── 1. Active mission in progress ──────────────────────────────────
        mission_active = (
            self.bb.get("mission/active")
            if self.bb.exists("mission/active")
            else False
        )
        if mission_active:
            return py_trees.common.Status.SUCCESS

        # ── 2. No pending request ───────────────────────────────────────────
        mission_request = (
            self.bb.get("mission/request")
            if self.bb.exists("mission/request")
            else None
        )
        if not mission_request or mission_request == "idle":
            return py_trees.common.Status.FAILURE

        # ── 3. Battery degraded ─────────────────────────────────────────────
        battery_degraded = (
            self.bb.get("battery_degraded")
            if self.bb.exists("battery_degraded")
            else False
        )
        if battery_degraded:
            return py_trees.common.Status.FAILURE

        # ── 4. All clear ────────────────────────────────────────────────────
        return py_trees.common.Status.SUCCESS


class MissionStatusTracker(py_trees.decorators.Decorator):
    """
    BTA-051: Tracks mission lifecycle and signals the result to MissionActionServer.

    Ownership contract
    ──────────────────
    WRITES (this class):
      mission/status       — "RUNNING" | "SUCCESS" | "FAILURE"
                             MissionActionServer.update() latches this value.
      mission/last_outcome — telemetry ("success" | "failure")
      mission/id           — per-mission unique id (telemetry)

    READS (this class):
      mission/active       — written exclusively by MissionActionServer
      mission/request      — written exclusively by MissionActionServer
      mission/type         — written exclusively by MissionActionServer

    This decorator NEVER writes mission/active, mission/request, or mission/type.
    Those keys are the sole responsibility of MissionActionServer, which uses them
    to drive the action protocol.  Writing them here would create a race condition
    between the synchronous tree tick and the asynchronous execute_callback loop.
    """

    def __init__(
        self,
        child: py_trees.behaviour.Behaviour,
        name: str = "MissionStatusTracker",
    ):
        super().__init__(name=name, child=child)
        self.node = None
        self.bb = self.attach_blackboard_client(name=self.name)

        # ── READ-ONLY (owned by MissionActionServer) ────────────────────────
        self.bb.register_key(key="mission/active",  access=py_trees.common.Access.READ)
        self.bb.register_key(key="mission/request", access=py_trees.common.Access.READ)
        self.bb.register_key(key="mission/type",    access=py_trees.common.Access.READ)

        # ── WRITE (owned by this class) ─────────────────────────────────────
        self.bb.register_key(key="mission/status",       access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/last_outcome", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="mission/id",           access=py_trees.common.Access.WRITE)

    def setup(self, **kwargs):
        self.node = kwargs["node"]

    def _now_sec(self) -> float:
        if self.node is None:
            return 0.0
        return self.node.get_clock().now().nanoseconds / 1e9

    def initialise(self) -> None:
        """
        Called once when the decorator transitions from INVALID → ticking.
        Only assigns a mission/id if one is not already set.
        Does NOT touch mission/active — that is MissionActionServer's job.
        """
        mission_id = (
            self.bb.get("mission/id")
            if self.bb.exists("mission/id")
            else ""
        )
        if not mission_id:
            now_sec = self._now_sec()
            self.bb.set("mission/id", f"m-{int(now_sec * 1000)}")

        # Signal that the subtree is now running
        self.bb.set("mission/status", "RUNNING")

    def update(self) -> py_trees.common.Status:
        """
        Mirrors the child's terminal status into mission/status so that
        MissionActionServer.update() can latch it in the same tick.

        Does NOT modify mission/active, mission/request, or mission/type.
        MissionActionServer._promote_next_mission / _clear_blackboard handle
        those keys after the action result is committed.

        Idempotency: once mission/status is SUCCESS or FAILURE, we do NOT
        overwrite it.  This prevents a subsequent tick (where
        MissionAdmissionGate returns FAILURE because the mission is still
        technically "active") from clobbering a valid SUCCESS with FAILURE.
        """
        # Guard: don't overwrite an already-terminal status
        try:
            current = self.bb.get("mission/status")
            if current in ("SUCCESS", "FAILURE"):
                return self.decorated.status
        except KeyError:
            pass

        child_status = self.decorated.status

        if child_status == py_trees.common.Status.SUCCESS:
            self.bb.set("mission/status",       "SUCCESS")
            self.bb.set("mission/last_outcome", "success")
            self.bb.set("mission/id",           "")   # reset for next mission

        elif child_status == py_trees.common.Status.FAILURE:
            self.bb.set("mission/status",       "FAILURE")
            self.bb.set("mission/last_outcome", "failure")
            self.bb.set("mission/id",           "")   # reset for next mission

        # RUNNING or INVALID: nothing to report yet
        return child_status