# Sancho Robot — Workspace Setup Guide

[← Back to Main README](../README.md)

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| **OS** | Ubuntu 22.04 LTS (Jammy Jellyfish) |
| **ROS 2** | Humble Hawksbill |
| **Build Tool** | `colcon` |
| **Python** | 3.10+ |
| **CMake** | 3.22+ |

### System Dependencies

```bash
sudo apt update && sudo apt install -y \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  ros-humble-nav2-bringup \
  ros-humble-navigation2 \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher \
  ros-humble-tf2-ros \
  ros-humble-cv-bridge \
  ros-humble-image-transport \
  ros-humble-pointcloud-to-laserscan \
  ros-humble-depthimage-to-laserscan \
  ros-humble-message-filters \
  ros-humble-tf-transformations \
  ros-humble-behaviortree-cpp-v3 \
  ros-humble-nav2-behavior-tree \
  portaudio19-dev \
  libfftw3-dev
```

### Python Dependencies

Several packages require Python libraries beyond the ROS 2 defaults:

```bash
pip3 install \
  pyaudio playsound soundfile pyannote.audio scipy requests \
  mediapipe dlib filterpy scikit-image \
  tensorflow tensorflow_hub scikit-learn \
  numpy opencv-python cvxopt
```

> **Note:** Some packages ship a `requirements.txt` (e.g., `sancho_audio`, `sancho_vision`, `sancho_perception`). Install them individually with `pip3 install -r <package>/requirements.txt` if needed.

---

## Build Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/MAPIRlab/sancho_robot.git
cd sancho_robot/ros2_ws
```

### 2. Install ROS Dependencies

```bash
# Initialize rosdep if not already done
sudo rosdep init  # only needed once
rosdep update

# Install all declared dependencies
rosdep install --from-paths src --ignore-src -r -y
```

### 3. Build the Workspace

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

> **Tip:** To build a specific package only:
> ```bash
> colcon build --symlink-install --packages-select sancho_bringup
> ```

### 4. Source the Workspace

```bash
source install/setup.bash
```

Add this to your `~/.bashrc` for persistence:

```bash
echo "source ~/sancho_robot/ros2_ws/install/setup.bash" >> ~/.bashrc
```

---

## Environment Variables

The robot requires API keys for certain HRI services. Copy the provided `.env` template at the repository root and ensure the variables are exported before launching:

```bash
set -a && source ../env && set +a
```

Key variables:
- `OPENAI_API_KEY` — OpenAI LLM access
- `GEMINI_API_KEY` — Google Gemini LLM access
- `HUGGING_FACE_API_KEY` — Hugging Face model access
- `PICOVOICE_API_KEY_SANCHO` — Wake-word engine

---

## Quick Start

### Physical Robot (Full Bringup)

This launches the complete physical robot stack: URDF, all hardware drivers, and the sensor processing layer.

```bash
ros2 launch sancho_bringup sancho_full_bringup.launch.py
```

### Navigation Stack

After bringup, launch the navigation stack in a separate terminal:

```bash
# Localization (AMCL with a pre-built map)
ros2 launch sancho_navigation localization.launch.py map:=/path/to/map.yaml

# Full navigation (planner + controller + collision monitor)
ros2 launch sancho_navigation navigation.launch.py
```

### SLAM (Map Creation)

```bash
ros2 launch sancho_navigation map_creation.launch.py
```

### Perception Pipeline

```bash
# Body pose detection + 3D projection + group detection
# (Lifecycle nodes — configure & activate via sancho_lifecycle_utils)
```

### Vision Pipeline (Face Recognition)

```bash
ros2 launch sancho_vision identification.launch.py
```

### Audio & Voice Assistant

```bash
# Hardware audio (mic capture)
ros2 launch sancho_audio audio_hardware.launch.py

# Audio processing (VAD, DOA)
ros2 launch sancho_audio audio_processing.launch.py

# Dialog core (assistant helper + assistant)
ros2 launch sancho_audio dialog_core.launch.py
```

### Behavioral Orchestrator

```bash
# Social interaction orchestrator
ros2 launch sancho_behavior sancho_interaction.launch.py
```

---

## Package Overview

The workspace contains **15 first-party packages** and **12 vendored third-party packages**:

```
src/
├── sancho_bringup/          ← 🚀 Start here
├── sancho_description/
├── sancho_hardware/
├── sancho_interfaces/
├── sancho_perception/
├── sancho_vision/
├── sancho_audio/
├── sancho_control/
├── sancho_navigation/
├── sancho_behavior/
├── sancho_bt_plugins/
├── sancho_hri/
├── sancho_web_bridge/
├── sancho_lifecycle_utils/
├── cliff_detector/
└── third_party_pkgs/
    ├── astra_camera/            ← Orbbec Astra driver
    ├── astra_camera_msgs/       ← Astra custom messages
    ├── interbotix_ptu/          ← WidowX pan-tilt driver
    ├── laser_scan_merger/       ← Multi-LiDAR fusion
    ├── urg_node2/               ← Hokuyo URG driver
    ├── usb_cam/                 ← USB camera driver
    ├── ranger_ros2/             ← AgileX Ranger ROS 2 driver
    ├── ugv_sdk/                 ← AgileX UGV SDK
    ├── ByteTrack/               ← Multi-object tracker
    ├── image_pipeline/          ← ROS 2 image processing
    ├── nav2_social_costmap_plugin/ ← Social-aware costmap layer
    └── people_msgs/             ← People-tracking messages
```

For detailed documentation on each package, see the [Repository Map](../README.md#repository-map) in the main README.
