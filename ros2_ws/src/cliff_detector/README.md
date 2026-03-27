[← Back to Main README](../../../README.md)

# cliff_detector

The `cliff_detector` package processes depth images to detect positive obstacles and drops (cliffs) such as stairs. It analyzes raw depth streams and publishes detected obstacle points for navigation safety.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `cliff_detector.launch.py` | Launches the cliff detector node with parameters from `config/params.yaml` |

---

## Nodes

### `cliff_detector` (C++)

Analyzes incoming depth images block by block, comparing pixel depths against a ground model based on the sensor's mount height and tilt angle. Detects areas that differ significantly from the expected ground plane (e.g., stairs, cliffs, ledges).

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/camera/depth/image_raw` | `sensor_msgs/msg/Image` | Raw depth image stream |
| `/camera/depth/camera_info` | `sensor_msgs/msg/CameraInfo` | Depth camera intrinsics (via `image_transport`) |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `points` | `geometry_msgs/msg/PolygonStamped` | Extracted obstacle/cliff points |
| `depth` | `sensor_msgs/msg/Image` | Debug depth image with cliff overlay (if `publish_depth` is true) |

### Services

*None*

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `range_min` | double | `0.5` | Minimum range to consider (m) |
| `range_max` | double | `5.0` | Maximum range to consider (m) |
| `depth_img_row_step` | int | `2` | Row step for processing |
| `depth_img_col_step` | int | `2` | Column step for processing |
| `cam_model_update` | bool | `false` | Continuously update camera model |
| `sensor_mount_height` | double | `0.4` | Sensor height from ground (m) |
| `sensor_tilt_angle` | double | `0.0` | Sensor tilt (rad) |
| `ground_margin` | double | `0.05` | Margin for ground classification (m) |
| `block_size` | int | `2` | Block size for image processing |
| `publish_depth` | bool | `false` | Enable debug depth image output |
| `used_depth_height` | int | `200` | Depth image subregion height |
| `block_points_thresh` | int | `10` | Min points in a block to flag obstacle |

---

## Lifecycle Information

This node is a standard `rclcpp::Node` — it does not implement the Lifecycle architecture.

---

## Dependencies

- **Internal:** *(none)*
- **External:** `rclcpp`, `sensor_msgs`, `image_geometry`, `image_transport`, `cv_bridge`, `geometry_msgs`
- **Build type:** `ament_cmake`
