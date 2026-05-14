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

    def initialise(self):
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
        percentage = battery_msg.percentage / 100.0

        current = battery_msg.current
        if current > 0.1:
            is_charging = True
        elif current < -0.1:
            is_charging = False
        else:
            is_charging = self.bb.is_charging if self.bb.exists("is_charging") else False

        if self._is_first_message:
            self.bb.has_greeted_charging = is_charging
            self._is_first_message = False
        else:
            if not is_charging:
                self.bb.has_greeted_charging = False
                self.bb.has_greeted_full = False
            else:
                self.bb.has_requested_charge = False

        # --- 1. CLEARING LOGIC (Requires unplugging) ---
        if not is_charging:
            if percentage >= self.THRESHOLD_DEGRADED:
                self._was_critical = False
                self._was_degraded = False

        # --- 2. TRIGGERING LOGIC ---
        if percentage <= self.THRESHOLD_CRITICAL:
            self._was_critical = True
            self._was_degraded = True 
        elif percentage <= self.THRESHOLD_DEGRADED:
            self._was_degraded = True

        # --- 3. UI/GREETING LOGIC ---
        if percentage >= self.THRESHOLD_RECOVERY and is_charging:
            # Handle the "Hi, I have enough battery" speech flag here
            pass

        # --- Write variables ---
        self.bb.battery_level = percentage
        self.bb.is_charging = is_charging
        self.bb.battery_critical = self._was_critical
        self.bb.battery_degraded = self._was_degraded

        return py_trees.common.Status.SUCCESS