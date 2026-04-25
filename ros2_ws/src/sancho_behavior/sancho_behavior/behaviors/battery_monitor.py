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
    """

    THRESHOLD_CRITICAL = 0.10
    THRESHOLD_DEGRADED = 0.15
    THRESHOLD_RECOVERY = 0.9

    def __init__(self, name: str = "BatteryMonitor"):
        super().__init__(name)

        self._was_critical = False
        self._was_degraded = False
        self._is_first_message = True

        # Blackboard client
        self.bb = self.attach_blackboard_client(name=self.name)

        self.bb.register_key(key="battery_msg", access=py_trees.common.Access.READ)
        self.bb.register_key(key="battery_level", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="battery_degraded", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="battery_critical", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="is_charging", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="has_greeted_charging", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="has_requested_charge", access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="has_greeted_full", access=py_trees.common.Access.WRITE)

    def initialize(self):
        self.bb.battery_critical = False
        self.bb.battery_degraded = False
        self.bb.battery_level = 1.0
        self.bb.is_charging = False
        self.bb.has_requested_charge = False
        self.bb.has_greeted_full = False

    def update(self) -> py_trees.common.Status:

        if not self.bb.exists("battery_msg") or self.bb.battery_msg is None:
            self.logger.warning("No battery message on blackboard yet")
            return py_trees.common.Status.FAILURE

        battery_msg = self.bb.battery_msg

        # --- Hardware Patch 1: Percentage Scaling ---
        # Hardware outputs 0-100 (e.g., 81.0), convert to ROS standard 0.0-1.0
        percentage = battery_msg.percentage / 100.0
        #percentage = 0.05 # --- TEMP OVERRIDE FOR TESTING ---

        # --- Hardware Patch 2: Charging Status ---
        # Hardware outputs status: 0 (UNKNOWN). Use current instead.
        # Negative current (-1.8A) means discharging, positive means charging.
        current = battery_msg.current
        # Hysteresis for charging detection to avoid flicker
        if current > 0.1:
            is_charging = True
        elif current < -0.1:
            is_charging = False
        else:
            is_charging = self.bb.is_charging if self.bb.exists("is_charging") else False

        if self._is_first_message:
            # If booted up while plugged in, pretend we already said thanks
            self.bb.has_greeted_charging = is_charging
            self._is_first_message = False
        else:
            # Normal operation: reset flags based on charging state
            if not is_charging:
                self.bb.has_greeted_charging = False
                self.bb.has_greeted_full = False
            else:
                self.bb.has_requested_charge = False

        # --- Write level ---
        self.bb.battery_level = percentage
        self.bb.is_charging = is_charging

        # --- Hysteresis logic ---
        # Degraded clears when reaching the recovery threshold (90%), regardless of charging state
        if percentage >= self.THRESHOLD_RECOVERY:
            self._was_degraded = False
        elif percentage < self.THRESHOLD_DEGRADED:
            self._was_degraded = True

        # Critical clears ONLY when battery is above degraded threshold AND not charging
        if not is_charging and percentage >= self.THRESHOLD_DEGRADED:
            self._was_critical = False
        elif percentage < self.THRESHOLD_CRITICAL:
            self._was_critical = True
            
        # --- Write flags ---
        self.bb.battery_critical = self._was_critical
        self.bb.battery_degraded = self._was_degraded

        return py_trees.common.Status.SUCCESS