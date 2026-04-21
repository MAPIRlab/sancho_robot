import math

import py_trees

from geometry_msgs.msg import PoseStamped
from tf_transformations import quaternion_from_euler


class _HeadGoalPublisherBase(py_trees.behaviour.Behaviour):
    """Common utilities for idle behaviours that command /head_goal."""

    def __init__(self, name: str):
        super().__init__(name)
        self.node = None
        self.head_pub = None

    def setup(self, **kwargs):
        self.node = kwargs["node"]
        self.head_pub = self.node.create_publisher(PoseStamped, "/head_goal", 10)

    def _publish_head_goal(self, yaw_deg: float, tilt_deg: float):
        yaw_rad = math.radians(yaw_deg)
        tilt_rad = math.radians(tilt_deg)
        q = quaternion_from_euler(0.0, tilt_rad, yaw_rad)

        msg = PoseStamped()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]
        self.head_pub.publish(msg)


class IdleHeadSweep(_HeadGoalPublisherBase):
    """
    BTA-040: Real idle scan behaviour.

    Performs a periodic horizontal sweep of the head while returning RUNNING.
    Non-blocking by design and immediately preemptible by higher layers.
    """

    def __init__(
        self,
        name: str = "IdleHeadSweep",
        sweep_angles_deg: list[float] | None = None,
        hold_sec: float = 3.0,
        tilt_deg: float = -20.0,
    ):
        super().__init__(name)
        self.sweep_angles_deg = sweep_angles_deg or [-45.0, -15.0, 15.0, 45.0, 0.0]
        self.hold_sec = hold_sec
        self.tilt_deg = tilt_deg
        self._idx = 0
        self._next_change_sec = None

    def initialise(self):
        self._next_change_sec = None

    def update(self) -> py_trees.common.Status:
        now_sec = self.node.get_clock().now().nanoseconds / 1e9

        if self._next_change_sec is None or now_sec >= self._next_change_sec:
            angle = self.sweep_angles_deg[self._idx]
            self._publish_head_goal(yaw_deg=angle, tilt_deg=self.tilt_deg)
            self._idx = (self._idx + 1) % len(self.sweep_angles_deg)
            self._next_change_sec = now_sec + self.hold_sec

        return py_trees.common.Status.RUNNING


class EnergySavingStandby(_HeadGoalPublisherBase):
    """
    BTA-041: Low-energy idle behaviour for degraded battery mode.

    Keeps the robot mostly static and only re-centers the head periodically,
    reducing unnecessary motion while still providing a deterministic RUNNING
    status for L4.
    """

    def __init__(
        self,
        name: str = "EnergySavingStandby",
        refresh_sec: float = 12.0,
        rest_tilt_deg: float = -30.0,
    ):
        super().__init__(name)
        self.refresh_sec = refresh_sec
        self.rest_tilt_deg = rest_tilt_deg
        self._next_refresh_sec = None

    def initialise(self):
        self._next_refresh_sec = None

    def update(self) -> py_trees.common.Status:
        now_sec = self.node.get_clock().now().nanoseconds / 1e9

        if self._next_refresh_sec is None or now_sec >= self._next_refresh_sec:
            self._publish_head_goal(yaw_deg=0.0, tilt_deg=self.rest_tilt_deg)
            self._next_refresh_sec = now_sec + self.refresh_sec

        return py_trees.common.Status.RUNNING
