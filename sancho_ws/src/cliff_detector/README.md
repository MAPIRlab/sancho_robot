# cliff_detector

**Role:** The `cliff_detector` package is responsible for processing depth images to detect positive obstacles and drops (cliffs) such as stairs. It processes raw depth streams and publishes the detected obstacles as polygon points, useful for robot navigation safety.

## Core Nodes

### `cliff_detector`
Extracts cliff points from depth images.
- **Specific Function:** Analyzes incoming depth images block by block, comparing pixel depths against a ground model based on the sensor's mount height and tilt angle. It detects and extracts areas that differ significantly from the expected ground (e.g., stairs/cliffs).

## API (Topics/Services)

### Subscribed Topics
- `/camera/depth/image_raw` (`sensor_msgs/msg/Image`) - The raw depth image stream from the depth camera.
- `/camera/depth/camera_info` (`sensor_msgs/msg/CameraInfo`) - Camera info corresponding to the depth image (handled automatically by `image_transport`).

### Published Topics
- `points` (`geometry_msgs/msg/PolygonStamped`) - The extracted obstacle/cliff points.
- `depth` (`sensor_msgs/msg/Image`) - Debug depth image with overlaid detected cliffs (only published if `publish_depth` is true).

### Services
- None

## Key Parameters

- `range_min` (double, default: 0.5): Minimum range in meters to consider.
- `range_max` (double, default: 5.0): Maximum range in meters to consider.
- `depth_img_row_step` (int, default: 2): Row step for depth image processing.
- `depth_img_col_step` (int, default: 2): Column step for depth image processing.
- `cam_model_update` (bool, default: false): Whether to continuously update the camera model from incoming info.
- `sensor_mount_height` (double, default: 0.4): Height of the depth sensor from the ground in meters.
- `sensor_tilt_angle` (double, default: 0.0): Tilt angle of the depth sensor in radians.
- `ground_margin` (double, default: 0.05): Allowed margin for depth measurements to still be considered ground.
- `block_size` (int, default: 2): Size of the block for image processing.
- `publish_depth` (bool, default: false): Enables publishing of the debug depth image.
- `used_depth_height` (int, default: 200): Subregion height of the depth image used for detection.
- `block_points_thresh` (int, default: 10): Threshold for number of points in a block to consider it an obstacle.

## Lifecycle Information
This node is natively an `rclcpp::Node` and not implemented as a Lifecycle node.
