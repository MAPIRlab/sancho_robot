# sancho_description

**Role:** The `sancho_description` package is responsible for the robot's physical and visual representations. It contains the URDF (Unified Robot Description Format) files, 3D meshes, and the launch files required to broadcast the robot's kinematic structure (TF tree) to the rest of the ROS 2 system. It also provides a utility node to unify joint state streams.

## Core Launch Files

### `description.launch.py`
- **Specific Function:** This is the primary launch file for the robot's physical description. It performs three key actions:
   1. Loads the `sancho_ranger.urdf` file and launches `robot_state_publisher` to broadcast the static TF transforms based on the merged joint states.
   2. Launches a standard `joint_state_publisher` to broadcast dummy values for fixed or non-actuated joints defined in the URDF, outputting to `/joint_states_urdf`.
   3. Launches the custom `joint_state_merger_node` to combine the physical and virtual joint states into a single unified stream.

## Core Nodes

### `joint_state_merger_node`
- **Specific Function:** A Python utility node designed to merge disparate joint state sources. Because physical servos (like the head pan/tilt) publish to one topic, and the static URDF joints publish to another, this node consumes both streams, prioritizes non-zero values if there are naming overlaps, and publishes a complete, unified `JointState` message at 50 Hz. This unified message is what `robot_state_publisher` ultimately consumes to accurately calculate the TF tree.

---

## API (Topics/Services)

### Subscribed Topics
- `/wxxms/joint_states` (`sensor_msgs/msg/JointState`): Real-time joint positions and velocities originating from the physical hardware (e.g., head servos).
- `/joint_states_urdf` (`sensor_msgs/msg/JointState`): Virtual or static joint states originating from the UI or `joint_state_publisher`.

### Published Topics
- `/joint_states_merged` (`sensor_msgs/msg/JointState`): The combined output stream consumed by `robot_state_publisher`. Published at a steady 50 Hz.
- `/tf` and `/tf_static` (`tf2_msgs/msg/TFMessage`): Published by `robot_state_publisher` based on the unified joint states and URDF kinematics.

---

## Key Parameters

### `description.launch.py`
- Does not extensively use runtime parameters, but internally maps the URDF file path `urdf/sancho_ranger.urdf` into the `robot_state_publisher`.

### `joint_state_merger_node`
- Has no ROS parameters; the 50 Hz cycle rate and topic names are internally hardcoded.

---

## Lifecycle Information

The nodes within this package are standard `rclpy.node.Node` implementations and do not utilize the ROS 2 Lifecycle architecture. They start running immediately upon execution.
