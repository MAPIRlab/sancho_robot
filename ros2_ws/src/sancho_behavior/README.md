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
