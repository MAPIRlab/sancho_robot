[← Back to Main README](../../../README.md)

# sancho_hardware

The `sancho_hardware` package serves as the Hardware Abstraction Layer (HAL) for the Sancho robot. It consolidates the initiation of all physical hardware drivers with Sancho-specific configurations, and provides custom nodes for bespoke hardware components (animated face, pan-tilt head).

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `ranger_wrapper.launch.py` | Launches the AgileX Ranger Mini v3 base chassis controller |
| `lidars_wrapper.launch.py` | Launches dual Hokuyo URG LiDAR instances (front + rear) |
| `astra_wrapper.launch.py` | Launches the Orbbec Astra RGB-D camera driver |
| `nose_cam.launch.py` | Launches the `usb_cam` driver for the head-mounted camera |
| `head.launch.py` | Initializes the `head_controller_node` + lower-level servo drivers |
| `face.launch.py` | Initializes the `face_node` C++ daemon |

---

## Nodes

### `face_node` (C++)

Controls an ESP32-driven animated face display over serial (`/dev/esp32`). Maps logical face states ("idle", "listening", "happy") to ESP32 commands. In "speaking" state, uses PortAudio to monitor PulseAudio output and sends RMS volume levels ("low", "medium", "high") for lip-sync animation.

### `head_controller_node` (Python)

Controls the WidowX WXXMS head servos in two modes:
- **IDLE:** Autonomous random micro-movements within parameterized limits.
- **TRACKING:** Converts incoming `PoseStamped` targets to joint commands. Reverts to IDLE after timeout.

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/face/mode` | `std_msgs/msg/String` | Face state commands ("idle", "listening", "happy", etc.) |
| `/head_goal` | `geometry_msgs/msg/PoseStamped` | Kinematic targets for the pan/tilt head |
| `/wxxms/joint_states` | `sensor_msgs/msg/JointState` | Servo feedback for tracking logic |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/wxxms/commands/joint_group` | `interbotix_xs_msgs/msg/JointGroupCommand` | Low-level position commands to head servos |

### Services Used

| Service | Type | Description |
|---------|------|-------------|
| `/wxxms/set_operating_modes` | `interbotix_xs_msgs/srv/OperatingModes` | Sets head servos to position-control mode |

---

## Parameters

### `face_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `send_interval_sec` | double | `0.1` | Audio sampling interval for lip-sync |

### `head_controller_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `idle_move_min_interval` | double | `5.0` | Min seconds between random IDLE gaze shifts |
| `idle_move_max_interval` | double | `8.0` | Max seconds between random IDLE gaze shifts |
| `pan_limit` | float[] | — | Pan safety limits |
| `tilt_limit` | float[] | — | Tilt safety limits |
| `tracking_timeout` | double | `5.0` | Seconds without `/head_goal` before reverting to IDLE |
| `profile_velocity` | int | — | Motor profile velocity |
| `profile_acceleration` | int | — | Motor profile acceleration |

---

## Dependencies

- **Internal:** `sancho_interfaces`
- **External:** `rclpy`, `rclcpp`, `std_msgs`, `portaudio`, `fftw3`, `interbotix_xs_msgs`
