import threading
import json

from importlib import import_module
from typing import Any, Optional

try:
    import sys
    if "--mock" in sys.argv:
        raise ImportError("Mock mode requested via command line argument")
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node

    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav2_msgs.action import NavigateToPose, Spin
    from sensor_msgs.msg import Image
    from std_srvs.srv import Trigger
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    class Node:
        def __init__(self, *args, **kwargs):
            pass
    class ActionClient:
        pass
    class PoseWithCovarianceStamped:
        pass
    class NavigateToPose:
        pass
    class Spin:
        pass
    class Image:
        pass
    class Trigger:
        pass

from .config import (
    BASE_FRAME_ID,
    CAMERA_TOPIC,
    IMAGE_CAPTURE_TIMEOUT_SEC,
    MAP_FRAME_ID,
    POSE_TIMEOUT_SEC,
    POSE_TOPIC,
    TF_TIMEOUT_SEC,
)
from .vision import ros_image_to_data_uri

try:
    CvBridge: Any = import_module("cv_bridge").CvBridge
    cv2: Any = import_module("cv2")
except Exception as exc:
    if ROS_AVAILABLE:
        raise ImportError(
            f"Failed to import OpenCV/cv_bridge: {exc}. Please ensure the ROS 2 environment is sourced."
        ) from exc
    else:
        CvBridge = None
        cv2 = None

try:
    Graph: Any = import_module("topology_graph.srv").Graph
    PlayTTS: Any = import_module("sancho_interfaces.action").PlayTTS
    Mission: Any = import_module("sancho_interfaces.action").Mission
    GetMission: Any = import_module("sancho_interfaces.srv").GetMission
except Exception as exc:
    if ROS_AVAILABLE:
        raise ImportError(
            f"Failed to import custom ROS 2 interfaces: {exc}. Make sure to source install/setup.bash."
        ) from exc
    else:
        Graph = None
        PlayTTS = None
        Mission = None
        GetMission = None

try:
    tf2_ros: Any = import_module("tf2_ros")
except Exception as exc:
    if ROS_AVAILABLE:
        raise ImportError(
            f"Failed to import tf2_ros: {exc}. Please ensure the ROS 2 environment is sourced."
        ) from exc
    else:
        tf2_ros = None


class SanchoBridgeNode(Node):
    def __init__(self):
        super().__init__("sancho_mcp_bridge_node")
        self.nav_action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.spin_action_client = ActionClient(self, Spin, "/spin")
        self.topo_graph_client = self.create_client(Graph, "/topology_graph/graph")

        self.cv_bridge = CvBridge()
        self.latest_image: Optional[Image] = None
        self.image_received_event = threading.Event()
        self.image_sub = self.create_subscription(
            Image,
            CAMERA_TOPIC,
            self._image_callback,
            10,
        )
        self.latest_pose: Optional[PoseWithCovarianceStamped] = None
        self.last_pose: Optional[PoseWithCovarianceStamped] = None
        self.pose_received_event = threading.Event()
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            POSE_TOPIC,
            self._pose_callback,
            10,
        )
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.tts_action_client = ActionClient(self, PlayTTS, "/play_tts")

        #######################################################
        # MISSION CLIENTS
        #######################################################
        self.mission_client = ActionClient(self, Mission, "mission_action")
        self.get_client = self.create_client(GetMission, "/bt/get_mission")
        self.pop_client = self.create_client(Trigger, "/bt/pop_mission")
        self.clear_client = self.create_client(Trigger, "/bt/clear_missions")

    def _image_callback(self, msg: Image):
        self.latest_image = msg
        self.image_received_event.set()

    def _pose_callback(self, msg: PoseWithCovarianceStamped):
        self.latest_pose = msg
        self.last_pose = msg
        self.pose_received_event.set()

    def sync_get_topological_nodes(self) -> list[dict[str, Any]]:
        if not self.topo_graph_client.wait_for_service(timeout_sec=5.0):
            return [
                {
                    "error": "/topology_graph/graph service not available after 5 seconds."
                }
            ]

        req = Graph.Request()
        req.cmd = "GetAllNodes"

        future = self.topo_graph_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.done():
            res = future.result()
            if res and res.success:
                return self._parse_topology_nodes(res.result)
            return [{"error": f"Command failed. {res.message if res else ''}"}]
        return [{"error": "Service call timed out."}]

    @staticmethod
    def _parse_topology_nodes(raw_nodes: list[str]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        allowed_types = {"space", "docking"}
        for raw in raw_nodes:
            parts = raw.split()
            if len(parts) < 6:
                parsed.append({"raw": raw, "error": "Unexpected node format"})
                continue

            node_id, name, node_type, x, y, z = parts[:6]
            if node_type.lower() not in allowed_types:
                continue
            parsed.append(
                {
                    "id": int(node_id),
                    "name": name,
                    "type": node_type,
                    "position": {
                        "x": float(x),
                        "y": float(y),
                        "z": float(z),
                    },
                    "raw": raw,
                }
            )
        return parsed

    def sync_navigate_to_pose(
        self,
        x: float,
        y: float,
        w: float = 1.0,
        z: float = 0.0,
        wait_for_result: bool = True,
    ) -> str:
        if not self.nav_action_client.wait_for_server(timeout_sec=5.0):
            return "Error: navigate_to_pose Action Server not available."

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(x)
        goal_msg.pose.pose.position.y = float(y)
        goal_msg.pose.pose.orientation.z = float(z)
        goal_msg.pose.pose.orientation.w = float(w)

        self.get_logger().info(
            f"Sending navigation goal to (x:{x}, y:{y}, z:{z}, w:{w})..."
        )

        future = self.nav_action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            return "Error: Goal send request timed out."

        goal_handle = future.result()
        if goal_handle is None or not getattr(goal_handle, "accepted", False):
            return "Error: Goal was rejected or timed out by server."

        if not wait_for_result:
            return "Goal accepted."

        self.get_logger().info("Goal accepted, waiting for result...")
        res_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, res_future)

        result = res_future.result()
        if result and result.status == 4:
            return "Navigation succeeded! Reached destination."
        return f"Navigation ended with status code: {result.status if result else 'Unknown'}"

    def sync_rotate_in_place(
        self,
        degrees: float,
        time_allowance_sec: float = 10.0,
        wait_for_result: bool = True,
    ) -> str:
        if not self.spin_action_client.wait_for_server(timeout_sec=5.0):
            return "Error: /spin Action Server not available."

        spin_goal = Spin.Goal()
        spin_goal.target_yaw = float(degrees) * 3.141592653589793 / 180.0
        if hasattr(spin_goal, "time_allowance"):
            spin_goal.time_allowance = rclpy.duration.Duration(
                seconds=float(time_allowance_sec)
            ).to_msg()

        self.get_logger().info(
            f"Sending spin goal: {degrees:.1f} deg (time_allowance={time_allowance_sec}s)."
        )

        future = self.spin_action_client.send_goal_async(spin_goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            return "Error: Spin goal send request timed out."

        goal_handle = future.result()
        if goal_handle is None or not getattr(goal_handle, "accepted", False):
            return "Error: Spin goal was rejected or timed out by server."

        if not wait_for_result:
            return "Spin goal accepted."

        res_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, res_future)

        result = res_future.result()
        if result and result.status == 4:
            return "Spin succeeded!"
        return f"Spin ended with status code: {result.status if result else 'Unknown'}"

    def sync_take_photo_raw(self) -> dict[str, str]:
        self.get_logger().info("Waiting for image...")
        self.image_received_event.clear()

        waited = 0.0
        while not self.image_received_event.is_set() and waited < IMAGE_CAPTURE_TIMEOUT_SEC:
            rclpy.spin_once(self, timeout_sec=0.1)
            waited += 0.1

        if not self.image_received_event.is_set() or self.latest_image is None:
            return {"error": f"Timeout waiting for image from {CAMERA_TOPIC}"}

        image_msg = self.latest_image
        self.latest_image = None

        try:
            data_uri = ros_image_to_data_uri(
                image_msg, self.cv_bridge, cv2
            )
            if "," in data_uri:
                _prefix, b64_data = data_uri.split(",", 1)
            else:
                b64_data = data_uri
            return {
                "type": "image",
                "mime_type": "image/jpeg",
                "data": b64_data,
            }
        except Exception as exc:
            return {"error": f"Error encoding image: {exc}"}

    def sync_get_current_pose(self) -> dict[str, Any]:
        self.get_logger().info("Waiting for pose...")
        self.pose_received_event.clear()

        waited = 0.0
        while not self.pose_received_event.is_set() and waited < POSE_TIMEOUT_SEC:
            rclpy.spin_once(self, timeout_sec=0.1)
            waited += 0.1

        if self.pose_received_event.is_set() and self.latest_pose is not None:
            pose_msg = self.latest_pose
            self.latest_pose = None
            stale = False
        else:
            pose_msg = self.last_pose
            stale = True

        if pose_msg is None:
            deadline = self.get_clock().now() + rclpy.duration.Duration(seconds=TF_TIMEOUT_SEC)
            last_exc: Exception | None = None

            while self.get_clock().now() < deadline:
                try:
                    transform = self.tf_buffer.lookup_transform(
                        MAP_FRAME_ID,
                        BASE_FRAME_ID,
                        rclpy.time.Time(),
                    )
                    trans = transform.transform.translation
                    rot = transform.transform.rotation
                    return {
                        "frame_id": transform.header.frame_id,
                        "stamp": {
                            "sec": transform.header.stamp.sec,
                            "nanosec": transform.header.stamp.nanosec,
                        },
                        "stale": False,
                        "source": "tf",
                        "position": {
                            "x": trans.x,
                            "y": trans.y,
                            "z": trans.z,
                        },
                        "orientation": {
                            "x": rot.x,
                            "y": rot.y,
                            "z": rot.z,
                            "w": rot.w,
                        },
                    }
                except Exception as exc:
                    last_exc = exc
                    rclpy.spin_once(self, timeout_sec=0.05)

            return {
                "error": (
                    f"Timeout waiting for pose from {POSE_TOPIC} and TF lookup failed: {last_exc}"
                )
            }

        pose = pose_msg.pose.pose
        return {
            "frame_id": pose_msg.header.frame_id,
            "stamp": {
                "sec": pose_msg.header.stamp.sec,
                "nanosec": pose_msg.header.stamp.nanosec,
            },
            "stale": stale,
            "source": "amcl_pose",
            "position": {
                "x": pose.position.x,
                "y": pose.position.y,
                "z": pose.position.z,
            },
            "orientation": {
                "x": pose.orientation.x,
                "y": pose.orientation.y,
                "z": pose.orientation.z,
                "w": pose.orientation.w,
            },
            "covariance": list(pose_msg.pose.covariance),
        }

    def sync_play_tts(self, text: str, model: str = "", speaker: str = "") -> str:
        if not self.tts_action_client.wait_for_server(timeout_sec=5.0):
            return "Error: /play_tts Action Server not available."

        goal_msg = PlayTTS.Goal()
        goal_msg.text = text
        goal_msg.model = model
        goal_msg.speaker = speaker

        self.get_logger().info(f"Sending TTS goal: '{text}'...")
        future = self.tts_action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            return "Error: TTS goal send request timed out."

        goal_handle = future.result()
        if goal_handle is None or not getattr(goal_handle, "accepted", False):
            return "Error: TTS Goal was rejected or timed out."

        res_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, res_future)

        result = res_future.result()
        if result and result.status == 4:
            res_val = result.result
            return (
                f"TTS Success: {res_val.message if hasattr(res_val, 'message') else 'Speech completed.'}"
            )
        return f"TTS ended with status code: {result.status if result else 'Unknown'}"

##############################################################
# MISSION RELATED METHODS
##############################################################

    def sync_execute_mission(self, mission_type: str, json_params: str) -> str:
        """Sends a mission goal to the BT action server and waits for the result."""
        if not self.mission_client.wait_for_server(timeout_sec=5.0):
            return "Error: BT mission_action server not available."
            
        goal_msg = Mission.Goal(mission_type=mission_type, json_parameters=json_params)
        future = self.mission_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            return "Error: Mission goal send request timed out."
        
        goal_handle = future.result()
        if goal_handle is None or not getattr(goal_handle, "accepted", False):
            return "Error: Mission goal was rejected by the BT."

        res_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, res_future)

        result = res_future.result()
        if result is None:
            return "Error: Mission result was None."

        # result.status: 4=SUCCEEDED, 5=CANCELED, 6=ABORTED
        status_code = result.status
        res_val = result.result
        if status_code == 4:
            return f"Mission succeeded: {res_val.final_message}"
        elif status_code == 5:
            return f"Mission canceled: {res_val.final_message}"
        else:
            return f"Mission ended (status {status_code}): {res_val.final_message}"

    def sync_get_mission(self) -> dict[str, Any]:
        if not self.get_client.wait_for_service(timeout_sec=5.0):
            return {"error": "/bt/get_mission service not available."}
        req = GetMission.Request()
        future = self.get_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        res = future.result()
        if res is None:
            return {"error": "Service call failed or timed out."}
        return {
            "mission_type": res.mission_type,
            "status": res.status,
            "parameters": res.json_parameters,
            "queue_info": res.message,
        }

    def sync_pop_mission(self) -> str:
        future = self.pop_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future)
        return future.result().message

    def sync_clear_missions(self) -> str:
        future = self.clear_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future)
        return future.result().message