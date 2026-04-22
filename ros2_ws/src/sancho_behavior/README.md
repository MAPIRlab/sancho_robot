[← Back to Main README](../../../README.md)

# sancho_behavior

The `sancho_behavior` package provides the high-level behavioral brain of the Sancho robot. It orchestrates transitions between searching for people, navigating to them, and initiating social interactions by coordinating the lifecycle states of perception, navigation, and audio modules.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `sancho_interaction.launch.py` | Launches the orchestrator and interaction manager |
| `attention.launch.py` | Launches the attention management subsystem |

---

## Nodes

### `orchestrator_node` (Python)

A high-level state machine handling the robot's main behavioral loop:
1. **BUSCANDO** (Searching) — Waiting for group waypoints
2. **NAVEGANDO** (Navigating) — Sending goals to Nav2 via `NavigateToPose`
3. **SOCIALIZANDO** (Interacting) — Activating the interaction manager

Dynamically toggles lifecycle states of `interaction_manager` and navigation nodes.

### `interaction_manager_node` (Python, Lifecycle)

Takes control during the SOCIALIZANDO state. Activates face detection pipelines, uses acoustic TDOA to orient the head toward speakers, requests the central face cluster, and initiates conversation flows via the Assistant Helper APIs.

### `attention_manager_node` (Python)

Manages the robot's attentional focus based on multi-modal inputs (visual face detections, acoustic DOA, and interaction state).

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/group_waypoint` | `geometry_msgs/msg/PoseStamped` | Target locations for navigation |
| `/face_detections` | `sancho_interfaces/msg/FaceDetectionArray` | Visual face data |
| `/sancho_audio/doa` | `std_msgs/msg/Float32` | Acoustic Direction of Arrival |
| `/amcl_pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | Localization quality (BT plugin) |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/head_goal` | `geometry_msgs/msg/PoseStamped` | Kinematic targets for pan/tilt head |

### Services Provided

| Service | Type | Description |
|---------|------|-------------|
| `/social_state` | `sancho_interfaces/srv/SocialState` | Interaction status reporting |
| `assistant_finished` | `std_srvs/srv/Trigger` | Audio assistant dialog completion |

### Services Consumed

| Service | Type | Description |
|---------|------|-------------|
| `~/change_state`, `~/get_state` | `lifecycle_msgs` | Lifecycle control for managed nodes |
| `/lifecycle_manager_navigation/manage_nodes` | `nav2_msgs/srv/ManageLifecycleNodes` | Pause/resume Nav2 |
| `/central_faces_cluster_node/get_central_cluster` | `sancho_interfaces/srv/GetCentralFaceCluster` | Central face cluster |
| `assistant/greet_people` | `sancho_interfaces/srv/GreetPeople` | Trigger greeting |

### Actions Used

| Action | Type | Description |
|--------|------|-------------|
| `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Send navigation goals |

---

## Parameters

### `orchestrator_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `nav_waypoint_topic` | string | `"/group_waypoint"` | Navigation goal input topic |
| `navigation_timeout` | double | `20.0` | Max navigation time (s) |
| `social_timeout` | double | `30.0` | Max interaction time (s) |

### `interaction_manager_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_face_attempts` | int | `3` | Attempts to find a face before fallback |
| `tdoa_angle_limit` | double | `90.0` | Max acoustic angle to act upon |
| `rotation_speed` | double | `0.3` | Orientation speed toward sound |
| `scan_angles` | list | `[0, 45, -45, 0]` | Search pattern if no faces in view |

---

## Lifecycle Information

| Node | `on_configure` | `on_activate` | `on_deactivate` |
|------|----------------|---------------|-----------------|
| `interaction_manager_node` | Prepares service clients for social state, face cluster, and greeting | Opens subscriptions to faces/DOA, starts interaction loop | Cleans up subscriptions, deactivates managed sub-nodes |

---

## Dependencies

- **Internal:** `sancho_interfaces`, `sancho_lifecycle_utils`
- **External:** `rclpy`

---

## L3/L4 Admission Contract

To keep a clear boundary between high-level missions (L3) and idle behavior
(L4), admission to L3 is handled in `main_tree.py` with explicit arbitration
rules:

1. L3 is admitted only if a formal objective exists (`group_waypoint_pose`).
2. New L3 admissions are blocked when `battery_degraded=true`.
3. After mission exit, a cooldown latch (`mission/cooldown_until`) blocks
	immediate re-entry to L3 to avoid L3<->L4 oscillation.

Mission execution details remain isolated in `mission_tree.py`, while policy
decisions live in the arbitration layer.

---

## Blackboard Namespace Conventions (BTA-075)

To avoid collisions and maintain clear data ownership, all Blackboard keys must follow these namespace prefixes:

- `layer/<name>/...`: Internal variables private to a specific layer (e.g., `layer/L1/...`).
- `mission/...`: Global arbitration state regarding the current L3 mission (e.g., `mission/active`, `mission/id`).
- `capability/<name>/...`: Variables shared by a reusable capability/proxy (e.g., `capability/tracking/active_until`).
- `config/...`: Global static or slowly changing configuration parameters (e.g., `config/dock_pose`).
- Global unstructured keys (like `hotword_event` or `battery_critical`) are legacy and will be gradually migrated to structured namespaces.

---

## Capability Tracking API (BTA-094)

The attention stack now exposes a minimal, reusable capability contract for tracking:

- Enable tracking:
	- Service: `/attention_manager/capability/tracking/enable`
	- Type: `std_srvs/srv/SetBool`
	- Request: `data=true`
- Disable tracking:
	- Service: `/attention_manager/capability/tracking/disable`
	- Type: `std_srvs/srv/Trigger`
- Set tracking mode:
	- Topic: `/attention_manager/capability/tracking/set_mode`
	- Type: `std_msgs/msg/String`
	- Typical values: `active`, `standby`, `post_interaction`
- Tracking TTL observability:
	- Topic: `/attention_manager/capability/tracking/active_until`
	- Type: `std_msgs/msg/Float32`

L2 (`preemption_tree`) and L3 (`mission_tree`) use this same contract to avoid
direct coupling to attention internals.

---

## How To Visualize Trees

From `ros2_ws/`:

1. Render static graph files (`.dot`, `.png`, `.svg`):
	 - `python3 scripts/render_tree.py src/sancho_behavior/sancho_behavior/trees/main_tree.py`
2. Open generated files:
	 - `render_main_tree.dot`
	 - `render_main_tree.png`
	 - `render_main_tree.svg`

Runtime snapshots are also printed in logs because `DisplaySnapshotVisitor`
is enabled in `main_tree.py`.
