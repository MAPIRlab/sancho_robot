[← Back to Main README](../../../README.md)

# sancho_control

The `sancho_control` package provides hardware-agnostic control logic for the Sancho robot. It houses the head tracking system, which converts 2D pixel positions of detected faces into pan/tilt servo commands to keep users centered in the camera's field of view.

---

## Nodes

### `head_control_face_tracker` (Lifecycle)

Visually tracks a target face using an Exponential Moving Average (EMA) pixel filter for smoothing. Computes angular error from the camera center using intrinsic calibrations, and applies a Proportional (P) controller to generate pan/tilt goals for the head servos.

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/sancho_perception/human_tracking` | `sancho_interfaces/msg/FaceDetectionArray` | Detected faces in camera frame |
| `/sancho_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Focal lengths and optical center for angular error computation |
| `/wxxms/joint_states` | `sensor_msgs/msg/JointState` | Current head servo positions |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/head_goal` | `geometry_msgs/msg/PoseStamped` | Desired pan/tilt angles encoded in quaternion orientation |

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `face_topic` | string | `"/sancho_perception/human_tracking"` | Input face detection topic |
| `head_goal_topic` | string | `"/head_goal"` | Output head goal topic |
| `camera_frame` | string | `"camera_frame"` | Frame ID in target message |
| `control_rate` | double | `10.0` | Control loop frequency (Hz) |
| `ema_alpha` | double | `0.2` | EMA smoothing factor (lower = smoother) |
| `p_gain_pan` | double | `0.8` | Proportional gain for horizontal tracking |
| `p_gain_tilt` | double | `0.8` | Proportional gain for vertical tracking |
| `timeout_no_detection` | double | `1.0` | Seconds before abandoning track |
| `pan_joint` | string | `"pan"` | Pan servo name in `joint_states` |
| `tilt_joint` | string | `"tilt"` | Tilt servo name in `joint_states` |

---

## Lifecycle Information

| Transition | Behavior |
|------------|----------|
| `on_configure` | Resolves parameters, creates publisher for `/head_goal` |
| `on_activate` | Subscribes to camera, face, and joint state topics; starts control loop timer |
| `on_deactivate` | Destroys timers and subscriptions, halts head commands |

---

## Dependencies

- **Internal:** `sancho_interfaces`
- **External:** `rclpy`, `geometry_msgs`, `sensor_msgs`, `std_msgs`, `lifecycle_msgs`, `tf_transformations`
