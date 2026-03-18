# sancho_perception

**Role:** The `sancho_perception` package provides the full human body perception pipeline. It uses Google's MoveNet model to detect human poses from camera images, converts 2D keypoints into 3D positions using depth data and TF, clusters detected people into social groups via DBSCAN, and generates navigation waypoints for the robot to approach detected individuals or groups. All core nodes implement the ROS 2 Lifecycle architecture.

## Core Nodes

### `movenet_inference_node` (Lifecycle)
- **Specific Function:** Runs the MoveNet TensorFlow model on incoming RGB images. Detects human poses (17 keypoints per person), publishes structured `PersonsPoses` messages with 2D keypoint coordinates, confidence scores, and bounding boxes. Also publishes inference timing metrics and annotated debug images with skeleton overlays.

### `movenet_postprocessing_node` (Lifecycle)
- **Specific Function:** Takes 2D pose detections from the inference node and synchronizes them with depth images using `message_filters`. Converts 2D keypoints into 3D positions using camera intrinsics and depth values. Transforms all detections into the `map` frame via TF2. Publishes `PoseArray` messages, `PersonsPoses` with 3D keypoints, RViz `MarkerArray` visualizations (skeleton lines, text labels), and `people_msgs/People` for Nav2 social costmap integration.

### `group_detection_node` (Lifecycle)
- **Specific Function:** Clusters detected persons into social groups using DBSCAN spatial clustering with silhouette score validation. Applies temporal filtering (stability windows, minimum detection counts) and spatial area thresholds to produce robust group detections. Publishes `GroupInfo` messages with group centroid and radius.

### `group_waypoint_generator_node` (Lifecycle)
- **Specific Function:** Receives `GroupInfo` messages and computes a safe navigation waypoint for the robot to approach the group. Considers the group radius, a configurable safety margin, and the robot's current position (via TF2). Applies a waypoint history filter to avoid unnecessary re-planning. Publishes `PoseStamped` goals oriented toward the group centroid.

### `single_person_detector_node` (Lifecycle)
- **Specific Function:** Tracks a single person from the pose array. Uses temporal and spatial association to maintain track continuity, with support for track IDs from upstream trackers. Publishes the tracked person's position as a `PoseStamped`.

### `single_person_waypoint_generator_node`
- **Specific Function:** Similar to the group waypoint generator but tailored for following a single detected person, computing approach waypoints with appropriate standoff distance.

### `relay_metrics_node` / `perception_test`
- **Specific Function:** Utility nodes for benchmarking and testing the perception pipeline.

---

## API (Topics/Services)

### Subscribed Topics
- Camera image topic (`sensor_msgs/msg/Image`): RGB input for MoveNet.
- Depth image topic (`sensor_msgs/msg/Image`): Depth input for 3D projection.
- Camera info topic (`sensor_msgs/msg/CameraInfo`): Intrinsic parameters.
- `/sancho_perception/human_poses` (`sancho_interfaces/msg/PersonsPoses`): 2D detections (consumed by postprocessing).
- `/human_pose/persons_poses` (`geometry_msgs/msg/PoseArray`): 3D pose array (consumed by group and single-person detectors).

### Published Topics
- `/sancho_perception/human_poses` (`sancho_interfaces/msg/PersonsPoses`): Raw 2D MoveNet detections.
- `/sancho_perception/human_tracking` (`sancho_interfaces/msg/PersonsPoses`): 3D postprocessed detections.
- `/sancho_perception/human_tracking_poses` (`geometry_msgs/msg/PoseArray`): 3D positions for downstream consumers.
- `/sancho_perception/group_info` (`sancho_interfaces/msg/GroupInfo`): Detected social group centroid and radius.
- `/group_waypoint` (`geometry_msgs/msg/PoseStamped`): Navigation goal to approach the detected group.
- `/single_person_waypoint` (`geometry_msgs/msg/PoseStamped`): Navigation goal to approach a single person.
- Various `/sancho_perception/*_markers` (`visualization_msgs/msg/MarkerArray`): RViz debug overlays.
- `/people` (`people_msgs/msg/People`): For Nav2 social costmap plugin.

---

## Key Parameters

### `movenet_inference_node`
- `model_name` (string): MoveNet model variant (e.g., `movenet_multipose_lightning`).
- `input_image_topic` / `output_image_topic` (string): I/O image topics.
- `min_score` (double): Minimum confidence threshold for detections.

### `group_detection_node`
- `dbscan_eps` (double): DBSCAN epsilon (max distance between cluster members, meters).
- `dbscan_min_samples` (int): Minimum people count to form a group.
- `stability_window` (int): Number of consecutive frames a group must be detected.
- `max_group_area` (double): Maximum bounding box area to qualify as a group.

### `group_waypoint_generator_node`
- `safety_margin` (double): Additional distance beyond group radius for the approach waypoint.
- `goal_hysteresis` (double): Minimum distance change to trigger a new goal publication.

### `single_person_detector_node`
- `max_jump_m` (double): Maximum allowed position jump between frames.
- `stability_count` (int): Frames before a detection is considered stable.
- `prefer_tracked_ids` (bool): Prioritize track ID continuity.

---

## Lifecycle Information

The following nodes implement the full ROS 2 Lifecycle architecture (`configure` → `activate` → `deactivate` → `cleanup`):
- `movenet_inference_node`
- `movenet_postprocessing_node`
- `group_detection_node`
- `group_waypoint_generator_node`
- `single_person_detector_node`

They are typically configured and activated by the `sancho_lifecycle_utils/node_configurator` or by the `sancho_behavior` orchestrator.
