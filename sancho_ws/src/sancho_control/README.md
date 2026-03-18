# sancho_control

**Role:** The `sancho_control` package provides specific hardware-agnostic control logic for the Sancho robot. Currently, it houses the head tracking system, which translates 2D pixel coordinates of detected faces into kinematic pan and tilt joint commands to keep users centered in the camera's view.

## Core Nodes

### `head_control_face_tracker`
- **Specific Function:** A LifecycleNode that visually tracks a target face. It computes an Exponential Moving Average (EMA) of the best detected face's pixel coordinates to smooth movements. Using camera intrinsic calibrations, it calculates the angular error from the center of the image and applies a Proportional (P) control algorithm to generate new Pan/Tilt goals, which are then enacted by the hardware interface.

---

## API (Topics/Services)

### Subscribed Topics
- `/sancho_perception/human_tracking` (`sancho_interfaces/msg/FaceDetectionArray`): Input data of detected faces in the camera frame.
- `/sancho_camera/camera_info` (`sensor_msgs/msg/CameraInfo`): Provides focal lengths ($f_x$, $f_y$) and optical centers ($c_x$, $c_y$) needed for converting pixel error to angular error.
- `/wxxms/joint_states` (`sensor_msgs/msg/JointState`): Real-time feedback of the current positions of the head servos.

### Published Topics
- `/head_goal` (`geometry_msgs/msg/PoseStamped`): Kinematic targets representing the desired pan and tilt angles. The angles are encoded in the `Pose.orientation` quaternion.

---

## Key Parameters

- `face_topic` (string, default: "/sancho_perception/human_tracking"): Input topic for face detections.
- `head_goal_topic` (string, default: "/head_goal"): Output topic for mechanical head goals.
- `camera_frame` (string, default: "camera_frame"): ID used in the target message header.
- `control_rate` (double, default: 10.0): Frequency in Hz of the internal PID tracking loop.
- `ema_alpha` (double, default: 0.2): Smoothing factor for the Exponential Moving Average filter applied to the target's pixel coordinates. Lower means smoother but slower to react.
- `p_gain_pan` (double, default: 0.8): Proportional gain for horizontal head tracking.
- `p_gain_tilt` (double, default: 0.8): Proportional gain for vertical head tracking.
- `timeout_no_detection` (double, default: 1.0): Time in seconds before giving up tracking if the target face is lost.
- `pan_joint` / `tilt_joint` (string, defaults: "pan", "tilt"): The internal names identifying the servos in `joint_states`.

---

## Lifecycle Information

The node extends `rclpy.lifecycle.LifecycleNode`:
- **`on_configure`**: Resolves parameters and sets up the unactivated publisher for `/head_goal`.
- **`on_activate`**: Activates subscriptions to the camera, face, and joint state topics. It initiates the core continuous control loop timer running at `control_rate`. Expects `CameraInfo` to be received before performing any tracking calculations.
- **`on_deactivate`**: Destroys the timers and subscriptions, safely halting physical robot movement commands.
