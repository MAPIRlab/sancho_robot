[← Back to Main README](../../../README.md)

# sancho_lifecycle_utils

The `sancho_lifecycle_utils` package provides a reusable utility node for automating the lifecycle management of other ROS 2 Managed (Lifecycle) Nodes. Instead of manually sending `configure` and `activate` transitions, the `node_configurator` handles it automatically using fully asynchronous service calls.

---

## Nodes

### `node_configurator`

Takes a list of lifecycle node names as a parameter. Every second, it polls each target node's available transitions. When `configure` becomes available, it triggers it. If the `activate` parameter is set, it subsequently triggers `activate`. Once all nodes reach their target state, the configurator shuts itself down.

---

## ROS 2 API

### Services Used (per target node)

| Service | Type | Description |
|---------|------|-------------|
| `/{node_name}/get_available_transitions` | `lifecycle_msgs/srv/GetAvailableTransitions` | Polls valid transitions |
| `/{node_name}/change_state` | `lifecycle_msgs/srv/ChangeState` | Triggers lifecycle transition |

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_names` | string[] | `["placeholder"]` | List of lifecycle node names to manage |
| `activate` | bool | `false` | Also activate nodes after configuration |

---

## Lifecycle Information

The `node_configurator` itself is a standard `rclpy.node.Node` (not a lifecycle node). It manages the lifecycle of *other* nodes.

---

## Dependencies

- **Internal:** *(none)*
- **External:** `rclpy`, `lifecycle_msgs`
