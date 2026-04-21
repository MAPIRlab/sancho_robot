import py_trees
import py_trees_ros
from sensor_msgs.msg import BatteryState


class BatteryMonitor(py_trees.behaviour.Behaviour):
    """
    Reads BatteryState from the blackboard (written by Battery2BB) and writes
    derived safety flags used by the priority tree.

    Blackboard Reads:
        /battery_msg (BatteryState): Raw message from Battery2BB

    Blackboard Writes:
        /battery_level     (float): Battery percentage 0.0-1.0
        /battery_degraded  (bool):  True below 15%, cleared above 90%
        /battery_critical  (bool):  True below 10%, cleared above 90%

    Thresholds:
        DEGRADED  < 15%  → stop accepting new tasks
        CRITICAL  < 10%  → dock immediately
        RECOVERY  > 90%  → clear both flags (hysteresis)
    """

    THRESHOLD_CRITICAL = 0.10
    THRESHOLD_DEGRADED = 0.15
    THRESHOLD_RECOVERY = 0.90

    def __init__(self, name: str = "BatteryMonitor"):
        super().__init__(name)

        # Internal hysteresis state — this is NOT an FSM, just memory
        # inside the node to avoid flag chattering around thresholds
        self._was_critical = False
        self._was_degraded = False

        # Blackboard client
        self.bb = self.attach_blackboard_client(name=self.name)

        self.bb.register_key(
            key="battery_msg",
            access=py_trees.common.Access.READ
        )
        self.bb.register_key(
            key="battery_level",
            access=py_trees.common.Access.WRITE
        )
        self.bb.register_key(
            key="battery_degraded",
            access=py_trees.common.Access.WRITE
        )
        self.bb.register_key(
            key="battery_critical",
            access=py_trees.common.Access.WRITE
        )
    
    def initialize(self):
        self.bb.battery_critical = False
        self.bb.battery_degraded = False
        self.bb.battery_level = 1.0

    def update(self) -> py_trees.common.Status:

        # --- Read raw message from blackboard ---
        battery_msg = self.bb.battery_msg

        if battery_msg is None:
            self.logger.warning("No battery message on blackboard yet")
            return py_trees.common.Status.FAILURE

        percentage = battery_msg.percentage  # ROS standard: 0.0 - 1.0
        is_charging = (
            battery_msg.power_supply_status
            == BatteryState.POWER_SUPPLY_STATUS_CHARGING
        )

        # --- Write level ---
        self.bb.battery_level = percentage

        # --- Hysteresis logic ---
        # Once a flag is set, it only clears when charging AND above recovery threshold.
        # This prevents chattering if percentage hovers around a threshold.
        if is_charging and percentage >= self.THRESHOLD_RECOVERY:
            self._was_critical = False
            self._was_degraded = False
        else:
            if percentage < self.THRESHOLD_CRITICAL:
                self._was_critical = True
                self._was_degraded = True  # critical implies degraded
            elif percentage < self.THRESHOLD_DEGRADED:
                self._was_degraded = True

        # --- Write flags ---
        self.bb.battery_critical = self._was_critical
        self.bb.battery_degraded = self._was_degraded

        return py_trees.common.Status.SUCCESS