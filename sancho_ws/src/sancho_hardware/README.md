# sancho_hardware

**Role:** The `sancho_hardware` package serves as the Hardware Abstraction Layer (HAL) for the entire Sancho robot. It consolidates the initiation of all physical hardware drivers. This includes customized wrapper launch files for off-the-shelf sensors (LiDARs, Realsense/Astra cameras, mobile base) that inject Sancho-specific configurations, as well as custom C++ and Python nodes required to interface with bespoke hardware components like the animated face and the WidowX-based pan-tilt head.

## Core Nodes

### `face_node` (C++)
- **Specific Function:** Controls an external LED/LCD animated face driven by an ESP32 microcontroller over a serial connection (`/dev/esp32`). It operates in two dimensions:
   1. **State machine mapping:** Subscribes to logical face states ("idle", "listening", "thinking") or emotions ("happy", "surprised", "sad") and sends the corresponding string commands to the ESP32.
   2. **Live Lip-Syncing:** When in the "speaking" state, the node uses PortAudio to actively monitor the PulseAudio output monitor (the sound physically leaving the robot's speakers). It calculates the RMS volume of the outgoing audio chunk every ~0.1s and sends discrete volume levels ("low", "medium", "high", etc.) to the ESP32, allowing the physical face to animate its mouth perfectly in sync with the spoken text-to-speech.

### `head_controller_node` (Python)
- **Specific Function:** Controls the physical servos of the robot's head (e.g., Dynamixel motors accessed via `interbotix_xs` interfaces). It manages two distinct modes:
  - **IDLE mode:** If no targets are being tracked, the head autonomously performs random, natural-looking micro-movements (pan/tilt) within predefined parameterized limits and time intervals, making the robot feel "alive."
  - **TRACKING mode:** When a target is received (e.g., from the `sancho_control` face tracker), it seamlessly interrupts the idle behavior, converts the requested `PoseStamped` orientation into raw joint position commands, and commands the hardware to look at the target. If the goal stream stops, it times out and reverts to IDLE mode.

---

## Core Launch Files (`/launch`)

These files wrap third-party driver nodes, injecting the specific configurations found in the `config/` directory.

- `astra_wrapper.launch.py`: Launches the RGB-D camera driver (e.g., Orbbec Astra).
- `lidars_wrapper.launch.py`: Launches dual instances of `rplidar_ros` for the front and rear scanning lasers.
- `ranger_wrapper.launch.py`: Launches the core base chassis controller (e.g., AgileX Ranger/Scout).
- `nose_cam.launch.py`: Launches the standard `usb_cam` driver for a secondary high-resolution camera.
- `head.launch.py`: Initializes the `head_controller_node` alongside any necessary lower-level servo drivers.
- `face.launch.py`: Initializes the `face_node` C++ daemon.

---

## API (Topics/Services)

### Subscribed Topics
- `/face/mode` (`std_msgs/msg/String`): Mode commands ("idle", "listening", "happy", etc.) consumed by `face_node`.
- `/head_goal` (`geometry_msgs/msg/PoseStamped`): Semantic kinematic targets consumed by `head_controller_node`.
- `/wxxms/joint_states` (`sensor_msgs/msg/JointState`): Feedback consumed by `head_controller_node` tracking logic.

### Published Topics
- `/wxxms/commands/joint_group` (`interbotix_xs_msgs/msg/JointGroupCommand`): Low-level position commands sent to the hardware servos by the `head_controller_node`.

### Services Used
- `/wxxms/set_operating_modes` (`interbotix_xs_msgs/srv/OperatingModes`): Used by the `head_controller_node` setup phase to explicitly lock the head servos into position-control mode.

---

## Key Parameters

### `face_node`
- `send_interval_sec` (double, default: 0.1): How frequently to sample the outgoing audio buffer and send an RMS string update to the ESP32.

### `head_controller_node`
- `idle_move_min_interval` / `idle_move_max_interval` (doubles, default: 5.0, 8.0): Boundaries in seconds for the random IDLE mode gaze shifts.
- `pan_limit` / `tilt_limit` (float arrays): Safety boundaries for kinematics, used for both random IDLE moves and clamping incoming TRACKING goals.
- `tracking_timeout` (double, default: 5.0): Seconds without a received `/head_goal` before the node gracefully drops back into IDLE mode.
- `profile_velocity` / `profile_acceleration` (ints): Motor profile dynamics applied when setting the operating mode on the servos.
