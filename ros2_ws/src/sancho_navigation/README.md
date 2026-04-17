[← Back to Main README](../../../README.md)

# sancho_navigation

The `sancho_navigation` package provides custom navigation logic on top of the standard Nav2 stack. It includes autonomous roaming behavior and ships the Nav2 configuration files, behavior trees, and pre-built maps.

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
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Velocity command for the base |

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
- **External:** `rclpy`, `nav2_msgs`, `geometry_msgs`, `tf2_ros`, `tf_transformations`, `numpy`
