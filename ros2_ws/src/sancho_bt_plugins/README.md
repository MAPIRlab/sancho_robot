[← Back to Main README](../../../README.md)

# sancho_bt_plugins

The `sancho_bt_plugins` package provides custom C++ BehaviorTree.CPP v3 plugin nodes for integration with the Nav2 navigation stack.

---

## Plugins

### `IsLocalized` (`ConditionNode`)

Subscribes to localization estimates (e.g., `/amcl_pose`) and returns `SUCCESS` if the robot's combined pose covariance (X + Y + Yaw) falls below a defined threshold. This gates navigation until the robot is confident about its position.

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/amcl_pose` *(configurable)* | `geometry_msgs/msg/PoseWithCovarianceStamped` | Localization pose estimate |

### Published Topics

*None*

### Services

*None*

---

## Parameters (BT Input Ports)

| Port | Type | Default | Description |
|------|------|---------|-------------|
| `topic` | string | `"/amcl_pose"` | Topic carrying `PoseWithCovarianceStamped` |
| `max_covariance` | double | `0.10` | Max allowable trace of X, Y, Yaw covariance |

---

## Dependencies

- **Internal:** *(none)*
- **External:** `rclcpp`, `nav2_behavior_tree`, `behaviortree_cpp_v3`, `geometry_msgs`
- **Build type:** `ament_cmake`
