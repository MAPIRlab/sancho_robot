[← Back to Main README](../../../README.md)

# sancho_navigation

The `sancho_navigation` package provides custom navigation logic on top of the standard Nav2 stack. It includes autonomous roaming behavior, a safety-critical Control Barrier Function (CBF) velocity filter, a semantic laser scan filter, and ships the Nav2 configuration files, behavior trees, and pre-built maps.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `navigation.launch.py` | Full Nav2 stack (planner + controller + collision monitor) |
| `localization.launch.py` | AMCL localization with a pre-built map |
| `map_creation.launch.py` | SLAM for building new maps |

### Launch Arguments

| Argument | Default | Applies To |
|----------|---------|------------|
| `map` | `maps/map.yaml` | `localization.launch.py` — path to the map YAML file |

---

## Nodes

### `roaming_node`

Autonomous exploration node. Generates random goal poses within a configurable local window, validates them via Nav2's `ComputePathToPose`, and sends validated goals via `NavigateToPose`. Supports a configurable home position (`set_home` service) and multiple generation strategies.

### `sancho_cbf_node`

Control Barrier Function (CBF) safety filter. Intercepts velocity commands from Nav2 (`/cmd_vel_nav2`), combines LiDAR data from both scanners, evaluates safety constraints at multiple chassis reference points, and solves a QP via a Hopfield neural network to produce safe velocity (`/cmd_vel`).

### `semantic_scan_filter`

Splits incoming laser scans into "persistent" (rear-facing) and "non-persistent" (front-facing) components based on a configurable field-of-view threshold. Uses TF for angle calculation.

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/cmd_vel_nav2` | `geometry_msgs/msg/Twist` | Raw Nav2 velocity commands (CBF input) |
| `/scan_1st` | `sensor_msgs/msg/LaserScan` | Front LiDAR data |
| `/scan_2nd` | `sensor_msgs/msg/LaserScan` | Rear LiDAR data |
| `/odom` | `nav_msgs/msg/Odometry` | Odometry feedback |
| `/amcl_pose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | Localization quality |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Safe velocity output from CBF |
| `/scan_persistent` | `sensor_msgs/msg/LaserScan` | Persistent (rear) scan component |
| `/scan_non_persistent` | `sensor_msgs/msg/LaserScan` | Non-persistent (front) scan component |

### Services Provided

| Service | Type | Description |
|---------|------|-------------|
| `set_home` | `sancho_interfaces/srv/SetHome` | Set/update roaming home position |

### Actions Used

| Action | Type | Description |
|--------|------|-------------|
| `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | Send navigation goals |
| `compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` | Validate random poses |

---

## Parameters

### `roaming_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_distance` | double | `5.0` | Max distance for random goals (m) |
| `max_attempts` | int | `20` | Attempts to find a valid pose |
| `timer_period` | double | `10.0` | Seconds between roaming attempts |

### `sancho_cbf_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `d_safe` | double | `0.35` | Minimum safe obstacle distance (m) |
| `gamma_cbf` | double | `10.0` | CBF strictness parameter |
| `lookahead` | double | `0.1` | Forward prediction point distance |

### `semantic_scan_filter`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `persistent_fov_deg` | double | `120.0` | FOV classified as "persistent" (°) |
| `max_angular_velocity` | double | `0.4` | Above this, scans pass unfiltered |
| `max_yaw_covariance` | double | `0.08` | Above this covariance, scans pass unfiltered |

---

## Shipped Resources

| Directory | Contents |
|-----------|----------|
| `config/` | Nav2 parameters: planner, controller, costmap, collision monitor, localization, SLAM, depth-to-laserscan |
| `maps/` | Pre-built occupancy grid maps (MAPIR lab, module 2.3) |
| `bt/` | Custom Nav2 Behavior Tree XML files |

---

## Dependencies

- **Internal:** `sancho_interfaces`
- **External:** `rclpy`, `nav2_msgs`, `geometry_msgs`, `tf2_ros`, `tf_transformations`, `numpy`, `cvxopt`
