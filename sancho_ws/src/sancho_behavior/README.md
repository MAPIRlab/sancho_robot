# sancho_behavior

**Role:** The `sancho_behavior` directory provides the high-level behavioral brain of the Sancho robot. It orchestrates the transitions between searching for people, navigating to them, and initiating social interactions by coordinating the lifecycle states of various perception, navigation, and audio modules. Additionally, this directory contains `sancho_bt_plugins`, a C++ sub-package providing custom Behavior Tree nodes for Nav2.

## Core Components

### `orchestrator_node` (Python)
- **Specific Function:** A high-level state machine handling the robot's main loop through three states: `BUSCANDO` (Searching), `NAVEGANDO` (Navigating), and `SOCIALIZANDO` (Interacting). It listens for group waypoints, sends navigation goals to Nav2 (`NavigateToPose`), and dynamically toggles the activation state of the `interaction_manager` and navigation nodes using Lifecycle services to prevent resource conflicts.

### `interaction_manager_node` (Python)
- **Specific Function:** A LifecycleNode that takes control when the robot is in the `SOCIALIZANDO` state. It ensures that the required face detection pipelines are active, uses acoustic TDOA (Time Difference of Arrival) to physically orient the robot's head towards a speaker (`/head_goal`), requests the central detected face cluster, and initiates conversation flows by triggering the Assistant Helper APIs.

### `sancho_bt_plugins` (C++)
- **Specific Function:** A separate `ament_cmake` package building a shared library of custom BehaviorTree CPP v3 plugins for Nav2.
- **Plugins Included:**
  - **`IsLocalized` (`ConditionNode`)**: Subscribes to localization estimates (e.g., `/amcl_pose`) and returns `SUCCESS` if the robot's pose covariance ($X$ + $Y$ + $Yaw$) is below a defined `max_covariance` threshold, essentially gating navigation until the robot is confident about its position.

---

## API (Topics/Services)

### Subscribed Topics
- `/group_waypoint` (`geometry_msgs/msg/PoseStamped`) - Target locations for the robot to move towards.
- `/face_detections` (`sancho_interfaces/msg/FaceDetectionArray`) - Visual face data.
- `/sancho_audio/doa` (`std_msgs/msg/Float32`) - Acoustic Direction of Arrival angle.
- `/amcl_pose` (`geometry_msgs/msg/PoseWithCovarianceStamped`) - Used by the `IsLocalized` BT plugin.

### Published Topics
- `/head_goal` (`geometry_msgs/msg/PoseStamped`) - Kinematic targets for the robot's pan/tilt head mechanisms.

### Services Provided
- `/social_state` (`sancho_interfaces/srv/SocialState`) - Used by the interaction manager to report its status (Ready, Finished, Error) back to the orchestrator.
- `assistant_finished` (`std_srvs/srv/Trigger`) - Callback endpoint for the audio assistant to signify the end of a dialog.

### Services Consumed
- `~/change_state` / `~/get_state` (`lifecycle_msgs/srv/ChangeState`, `GetState`) - Controls numerous nodes including `/face_manager`, `/face_detector`, etc.
- `/lifecycle_manager_navigation/manage_nodes` (`nav2_msgs/srv/ManageLifecycleNodes`) - To pause/resume Nav2 execution.
- `/central_faces_cluster_node/get_central_cluster` (`sancho_interfaces/srv/GetCentralFaceCluster`)
- `assistant/greet_people` (`sancho_interfaces/srv/GreetPeople`)
- Action Client: `navigate_to_pose` (`nav2_msgs/action/NavigateToPose`)

---

## Key Parameters

### `orchestrator_node`
- `nav_waypoint_topic` (string, default: "/group_waypoint"): Topic to receive navigation goals.
- `navigation_timeout` (double, default: 20.0): Max time in seconds for a navigation action before giving up.
- `social_timeout` (double, default: 30.0): Max time in seconds allowed for a social interaction before timing out.

### `interaction_manager_node`
- `max_face_attempts` (int, default: 3): Number of attempts to find a face before fallback.
- `tdoa_angle_limit` (double, default: 90.0): Max acoustic angle to act upon.
- `rotation_speed` (double, default: 0.3): Speed setting for orienting towards sound.
- `scan_angles` (list, default: [0.0, 45.0, -45.0, 0.0]): Pre-defined search pattern if no faces are in view.

### `IsLocalized` (BT Plugin Input Ports)
- `topic` (string, default: "/amcl_pose"): Topic carrying `PoseWithCovarianceStamped`.
- `max_covariance` (double, default: 0.10): Maximum allowable trace of the $X, Y, Yaw$ covariance matrix.

---

## Lifecycle Information

The `interaction_manager_node` implements the standard Lifecycle state machine:
- **`on_configure`**: Prepares service clients for `/social_state`, `/central_face_cluster`, and the TTS `greet_people` assistant service. Verifies that external prerequisite nodes (like detectors) are identifiable.
- **`on_activate`**: Opens subscriptions to hardware inputs (`/face_detections`, `/sancho_audio/doa`) and spins up the main interaction loop timer traversing states like checking TDOA wait times, scanning limits, and requesting Assistant interactions.
- **`on_deactivate`**: Cleans up subscriptions and gracefully deactivates managed sub-nodes like the `face_manager`.
