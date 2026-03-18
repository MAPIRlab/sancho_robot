# sancho_lifecycle_utils

**Role:** The `sancho_lifecycle_utils` package provides a reusable utility node for automating the lifecycle management of other ROS 2 Managed (Lifecycle) Nodes. Instead of manually sending `configure` and `activate` transitions, this package's `node_configurator` node handles it automatically and reliably using fully asynchronous service calls.

## Core Nodes

### `node_configurator`
- **Specific Function:** Takes a list of lifecycle node names as a parameter. Every second, it polls each target node's available transitions. When the `configure` transition becomes available, it triggers it. If the `activate` parameter is also set, it will subsequently trigger the `activate` transition. Once all specified nodes have reached their target state, the configurator automatically shuts itself down.

---

## API (Topics/Services)

### Services Used (per target node)
- `/{node_name}/get_available_transitions` (`lifecycle_msgs/srv/GetAvailableTransitions`): Polls which lifecycle transitions are currently valid.
- `/{node_name}/change_state` (`lifecycle_msgs/srv/ChangeState`): Triggers a specific lifecycle transition.

---

## Key Parameters

- `node_names` (string array, default: ["placeholder"]): List of lifecycle node names to manage.
- `activate` (bool, default: false): If true, also activates each node after successful configuration.

---

## Lifecycle Information

The `node_configurator` node itself is a standard `rclpy.node.Node` (not a lifecycle node). It is designed to manage the lifecycle of *other* nodes.
