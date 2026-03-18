# sancho_navigation

**Role:** The `sancho_navigation` package provides custom navigation logic on top of the standard Nav2 stack. It includes autonomous roaming behavior, a safety-critical Control Barrier Function (CBF) velocity filter, and a semantic laser scan filter. It also ships the Nav2 configuration files, behavior trees, and pre-built maps required for deployment.

## Core Nodes

### `roaming_node`
- **Specific Function:** An autonomous exploration node. It generates random goal poses within a configurable local window around the robot's current position, validates them asynchronously using Nav2's `ComputePathToPose` action (checking path length and reachability), and then sends the validated goal via `NavigateToPose`. It supports a configurable home position (via a `set_home` service), multiple generation strategies (local/global/home-based), and uses TF lookups to track the robot's current position.

### `sancho_cbf_node`
- **Specific Function:** A Control Barrier Function (CBF) safety filter. It intercepts velocity commands from Nav2 (`/cmd_vel_nav2`), combines LiDAR data from both front and rear scanners, evaluates safety constraints at multiple reference points on the robot chassis, and solves a Quadratic Program (QP) using a custom Hopfield neural network solver to produce a safe velocity command (`/cmd_vel`) that is as close to the desired command as possible while guaranteeing collision avoidance.

### `semantic_scan_filter`
- **Specific Function:** Splits incoming laser scans into "persistent" (rear-facing) and "non-persistent" (front-facing) components based on a configurable field-of-view threshold. It uses TF to transform laser points into the robot's base frame for angle calculation. This is used to feed different costmap layers with different observation persistence settings, improving navigation robustness.

---

## API (Topics/Services)

### Subscribed Topics
- `/cmd_vel_nav2` (`geometry_msgs/msg/Twist`): Raw Nav2 velocity commands (consumed by CBF node).
- `/scan_1st`, `/scan_2nd` (`sensor_msgs/msg/LaserScan`): Raw LiDAR data.
- `/odom` (`nav_msgs/msg/Odometry`): Odometry for angular velocity feedback.
- `/amcl_pose` (`geometry_msgs/msg/PoseWithCovarianceStamped`): Localization quality feedback.

### Published Topics
- `/cmd_vel` (`geometry_msgs/msg/Twist`): Safe velocity output from CBF node.
- `/scan_persistent`, `/scan_non_persistent` (`sensor_msgs/msg/LaserScan`): Filtered scan outputs.

### Services Provided
- `set_home` (`sancho_interfaces/srv/SetHome`): Set or update the roaming home position.

### Actions Used
- `navigate_to_pose` (`nav2_msgs/action/NavigateToPose`)
- `compute_path_to_pose` (`nav2_msgs/action/ComputePathToPose`)

---

## Key Parameters

### `roaming_node`
- `max_distance` (double, default: 5.0): Maximum distance from current position for random goals.
- `max_attempts` (int, default: 20): Attempts to find a valid random pose before giving up.
- `timer_period` (double, default: 10.0): Seconds between roaming attempts.

### `sancho_cbf_node`
- `d_safe` (double, default: 0.35): Minimum safe distance to obstacles (meters).
- `gamma_cbf` (double, default: 10.0): CBF strictness parameter.
- `lookahead` (double, default: 0.1): Forward prediction point distance.

### `semantic_scan_filter`
- `persistent_fov_deg` (double, default: 120.0): Field of view (degrees) classified as "persistent" (rear).
- `max_angular_velocity` (double, default: 0.4): Above this, scans pass through unfiltered.
- `max_yaw_covariance` (double, default: 0.08): Above this covariance, scans pass through unfiltered.

---

## Shipped Resources

- `config/`: Nav2 parameters, costmap settings, controller configurations.
- `maps/`: Pre-built occupancy grid maps.
- `bt/`: Custom Nav2 Behavior Tree XML files.
- `launch/`: Launch files for different navigation configurations.
