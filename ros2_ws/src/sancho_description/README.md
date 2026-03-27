[← Back to Main README](../../../README.md)

# sancho_description

The `sancho_description` package defines the robot's physical and visual representation. It contains the URDF model, 3D meshes, and the launch files required to broadcast the kinematic structure (TF tree) to the rest of the ROS 2 system.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `description.launch.py` | Loads `sancho_ranger.urdf`, launches `robot_state_publisher`, `joint_state_publisher` (→ `/joint_states_urdf`), and the custom `joint_state_merger_node`. |

---

## Nodes

### `joint_state_merger_node`

Merges disparate joint state sources into a unified stream. Physical servos (head pan/tilt) publish to `/wxxms/joint_states`, while static URDF joints publish to `/joint_states_urdf`. The merger prioritizes non-zero values on name overlaps and publishes the combined message at **50 Hz**.

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/wxxms/joint_states` | `sensor_msgs/msg/JointState` | Real-time positions from physical head servos |
| `/joint_states_urdf` | `sensor_msgs/msg/JointState` | Virtual/static joints from `joint_state_publisher` |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/joint_states_merged` | `sensor_msgs/msg/JointState` | Unified stream consumed by `robot_state_publisher` (50 Hz) |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | Transform tree from URDF kinematics |

---

## Parameters

| Node | Parameter | Default | Description |
|------|-----------|---------|-------------|
| `joint_state_merger_node` | *(none)* | — | 50 Hz rate and topic names are hardcoded |

---

## URDF Structure (`sancho_ranger.urdf`)

```
base_footprint
 └── base_link (Ranger Mini v3 chassis)
      ├── fr_Link, fl_Link, br_Link, bl_Link (4 wheels)
      ├── laser_front (front LiDAR)
      ├── laser_back (rear LiDAR)
      ├── astra_camera_link (Orbbec Astra RGB-D)
      └── body_link (body structure)
           └── turret_pan_link (pan joint)
                └── turret_tilt_link (tilt joint)
                     └── head_link
                          └── nose_camera_link (USB camera)
```

---

## Dependencies

- **Internal:** *(none)*
- **External:** `robot_state_publisher`, `joint_state_publisher`, `rviz2`, `urdf`
