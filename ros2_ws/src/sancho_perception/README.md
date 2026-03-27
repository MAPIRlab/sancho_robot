[← Back to Main README](../../../README.md)

# sancho_perception

The `sancho_perception` package provides the full human body perception pipeline. It uses Google's MoveNet to detect human poses from camera images, converts 2D keypoints into 3D positions using depth data and TF, clusters detected people into social groups via DBSCAN, and generates navigation waypoints. All core nodes implement the ROS 2 Lifecycle architecture.

---

## Nodes

| Node | Type | Description |
|------|------|-------------|
| `movenet_inference_node` | Lifecycle | Runs MoveNet TensorFlow model on RGB images, publishes 2D keypoints and debug overlays |
| `movenet_postprocessing_node` | Lifecycle | Synchronizes 2D poses with depth, projects to 3D via camera intrinsics + TF2, publishes `PoseArray` and `people_msgs/People` |
| `group_detection_node` | Lifecycle | Clusters persons into social groups using DBSCAN with silhouette validation and temporal filtering |
| `group_waypoint_generator_node` | Lifecycle | Computes safe approach waypoints for detected groups considering radius and safety margin |
| `single_person_detector_node` | Lifecycle | Tracks a single person with temporal/spatial association |
| `single_person_waypoint_generator_node` | Standard | Computes approach waypoints for a single tracked person |
| `relay_metrics_node` / `perception_test` | Standard | Benchmarking and testing utilities |

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| *(camera image topic)* | `sensor_msgs/msg/Image` | RGB input for MoveNet |
| *(depth image topic)* | `sensor_msgs/msg/Image` | Depth for 3D projection |
| *(camera info topic)* | `sensor_msgs/msg/CameraInfo` | Camera intrinsic parameters |
| `/sancho_perception/human_poses` | `sancho_interfaces/msg/PersonsPoses` | 2D detections (→ postprocessing) |
| `/human_pose/persons_poses` | `geometry_msgs/msg/PoseArray` | 3D poses (→ group/single-person nodes) |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/sancho_perception/human_poses` | `sancho_interfaces/msg/PersonsPoses` | Raw 2D MoveNet detections |
| `/sancho_perception/human_tracking` | `sancho_interfaces/msg/PersonsPoses` | 3D postprocessed detections |
| `/sancho_perception/human_tracking_poses` | `geometry_msgs/msg/PoseArray` | 3D positions for downstream |
| `/sancho_perception/group_info` | `sancho_interfaces/msg/GroupInfo` | Group centroid and radius |
| `/group_waypoint` | `geometry_msgs/msg/PoseStamped` | Nav goal for group approach |
| `/single_person_waypoint` | `geometry_msgs/msg/PoseStamped` | Nav goal for single-person approach |
| `/sancho_perception/*_markers` | `visualization_msgs/msg/MarkerArray` | RViz debug overlays |
| `/people` | `people_msgs/msg/People` | For Nav2 social costmap plugin |

---

## Parameters

### `movenet_inference_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_name` | string | — | MoveNet variant (e.g., `movenet_multipose_lightning`) |
| `input_image_topic` | string | — | Input image topic |
| `output_image_topic` | string | — | Debug output image topic |
| `min_score` | double | — | Minimum confidence threshold |

### `group_detection_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dbscan_eps` | double | — | Max distance between cluster members (m) |
| `dbscan_min_samples` | int | — | Min people count for a group |
| `stability_window` | int | — | Consecutive frames required |
| `max_group_area` | double | — | Max bounding box area for groups |

### `group_waypoint_generator_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `safety_margin` | double | — | Extra distance beyond group radius |
| `goal_hysteresis` | double | — | Min distance change to publish new goal |

### `single_person_detector_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_jump_m` | double | — | Max allowed position jump between frames |
| `stability_count` | int | — | Frames before detection is stable |
| `prefer_tracked_ids` | bool | — | Prioritize track ID continuity |

---

## Lifecycle Information

All core nodes follow the standard Lifecycle architecture (`configure` → `activate` → `deactivate` → `cleanup`):
- `movenet_inference_node`
- `movenet_postprocessing_node`
- `group_detection_node`
- `group_waypoint_generator_node`
- `single_person_detector_node`

They are typically configured and activated by `sancho_lifecycle_utils/node_configurator` or the `sancho_behavior` orchestrator.

---

## Dependencies

- **Internal:** `sancho_interfaces` *(implicit)*
- **External:** `rclpy`, `sensor_msgs`, `geometry_msgs`, `cv_bridge`, `image_transport`, `tf2_ros`, `numpy`, `opencv-python`, `tensorflow`, `tensorflow_hub`, `scikit-learn`, `tf_transformations`, `message_filters`
