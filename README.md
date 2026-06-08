# 🤖 Sancho Robot

**Sancho** is a socially-aware mobile robot built on the AgileX Ranger Mini v3 platform. It autonomously navigates indoor environments, detects and recognizes people using computer vision and body-pose estimation, holds conversations powered by LLMs, and physically orients its animated head and face toward whoever is speaking — all orchestrated through a modular ROS 2 architecture.

> Developed by the [MAPIRlab](https://mapir.isa.uma.es/) research group at the University of Málaga.

---

## Demonstration Video

A video demonstration of the robot and its hierarchical decision-making architecture is available on YouTube:

📺 **https://youtu.be/1JcaW7hJzJc**

The video showcases autonomous roaming, human-initiated task assignment through speech interaction, mission execution, task interruption, and battery-aware priority management using Behavior Trees.

---

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              sancho_bringup                                 │
│                    (Primary Entry Point — Launch Hub)                        │
│  ┌──────────────────┐  ┌───────────────────┐  ┌─────────────────────────┐   │
│  │ sancho_description│  │  sancho_hardware  │  │   Processing Layer      │   │
│  │  (URDF / TF)     │  │  (HAL / Drivers)  │  │ (Scan Merger + Filter)  │   │
│  └──────────────────┘  └───────────────────┘  └─────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
         │                        │                         │
         ▼                        ▼                         ▼
┌─────────────────┐   ┌───────────────────┐   ┌──────────────────────────────┐
│ sancho_perception│   │  sancho_vision    │   │    sancho_navigation         │
│ (MoveNet Body   │──▶│ (Face Detection/  │   │ (Nav2 + CBF Safety +         │
│  Pose Pipeline) │   │  Recognition/GUI) │   │  Roaming + Semantic Filter)  │
└─────────────────┘   └───────────────────┘   └──────────────────────────────┘
         │                     │                         │
         ▼                     ▼                         ▼
┌─────────────────┐  ┌────────────────┐    ┌──────────────────────────────────┐
│ sancho_control   │  │ sancho_audio   │    │      sancho_behavior             │
│ (Head Tracking   │  │ (Mic Capture / │    │ (Orchestrator State Machine +    │
│  P-Controller)   │  │  VAD / DOA /   │    │  Interaction Manager +           │
│                  │  │  Wake Word /   │    │  sancho_bt_plugins for Nav2)     │
│                  │  │  Assistant)    │    │                                  │
└─────────────────┘  └────────────────┘    └──────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           sancho_hri                                       │
│           (LLM / STT / TTS Provider Gateway + Conversational AI)           │
└────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────┐   ┌────────────────────┐   ┌─────────────────────────┐
│ sancho_web_bridge │   │ sancho_interfaces  │   │ sancho_lifecycle_utils  │
│ (WebSocket /     │   │ (Custom msgs/srvs/ │   │ (Lifecycle Node         │
│  REST API)       │   │  actions)          │   │  Auto-Configurator)     │
└──────────────────┘   └────────────────────┘   └─────────────────────────┘
```

---

## Repository Map

| Package | Description |
|---------|-------------|
| [**sancho_bringup**](ros2_ws/src/sancho_bringup/README.md) | 🚀 **Primary entry point.** Top-level launch files that bring up the robot description, hardware drivers, and processing layers. |
| [**sancho_description**](ros2_ws/src/sancho_description/README.md) | URDF model, 3D meshes, and TF tree broadcasting for the Ranger Mini v3 platform. |
| [**sancho_hardware**](ros2_ws/src/sancho_hardware/README.md) | Hardware Abstraction Layer — driver wrappers for LiDARs, cameras, base, head servos, and animated face. |
| [**sancho_interfaces**](ros2_ws/src/sancho_interfaces/README.md) | All custom ROS 2 message (33), service (31), and action (1) definitions. |
| [**sancho_perception**](ros2_ws/src/sancho_perception/README.md) | Human body pose estimation (MoveNet), 3D projection, social group detection via DBSCAN, and waypoint generation. |
| [**sancho_vision**](ros2_ws/src/sancho_vision/README.md) | Face detection, recognition, body-face fusion tracking, spatial clustering, and HRI GUI. |
| [**sancho_audio**](ros2_ws/src/sancho_audio/README.md) | Full audio pipeline — microphone capture, VAD, DOA estimation, wake word, and conversational assistant logic. |
| [**sancho_control**](ros2_ws/src/sancho_control/README.md) | Head tracking P-controller that converts face pixel positions into pan/tilt servo commands. |
| [**sancho_navigation**](ros2_ws/src/sancho_navigation/README.md) | Nav2 configuration, autonomous roaming, CBF safety filter, semantic scan splitting, maps and behavior trees. |
| [**sancho_behavior**](ros2_ws/src/sancho_behavior/README.md) | High-level behavioral orchestrator (Search → Navigate → Socialize state machine) and interaction manager. |
| [**sancho_bt_plugins**](ros2_ws/src/sancho_bt_plugins/README.md) | Custom C++ BehaviorTree.CPP v3 plugins for Nav2 (e.g., `IsLocalized` condition). |
| [**sancho_hri**](ros2_ws/src/sancho_hri/README.md) | Provider-agnostic LLM, STT, and TTS gateways plus the `sancho_ai` conversational brain with per-user memory. |
| [**sancho_web_bridge**](ros2_ws/src/sancho_web_bridge/README.md) | WebSocket-based ROS bridge, REST API, web assistant, session and database management. |
| [**sancho_lifecycle_utils**](ros2_ws/src/sancho_lifecycle_utils/README.md) | Utility node for automated lifecycle configuration and activation of managed nodes. |
| [**cliff_detector**](ros2_ws/src/cliff_detector/README.md) | Depth-image-based cliff and stair detection for navigation safety. |

> Third-party dependencies are vendored in [`ros2_ws/src/third_party_pkgs/`](ros2_ws/src/third_party_pkgs/) and include `astra_camera`, `interbotix_ptu`, `laser_scan_merger`, `urg_node2`, `usb_cam`, `ranger_ros2`, `ugv_sdk`, `ByteTrack`, `image_pipeline`, `nav2_social_costmap_plugin`, and `people_msgs`.

---

## Hardware Stack

| Component | Model / Driver | Purpose |
|-----------|---------------|---------|
| **Mobile Base** | AgileX Ranger Mini v3 (`ranger_ros2` / `ugv_sdk`) | 4WD skid-steer chassis, odometry, velocity control |
| **Front LiDAR** | Hokuyo URG (`urg_node2`) | Forward 2D obstacle scanning (`/scan_1st`) |
| **Rear LiDAR** | Hokuyo URG (`urg_node2`) | Rear 2D obstacle scanning (`/scan_2nd`) |
| **RGB-D Camera** | Orbbec Astra (`astra_camera`) | RGB + depth for perception, face detection, and cliff detection |
| **Nose Camera** | USB Camera (`usb_cam`) | High-resolution front-facing camera mounted on head |
| **Pan/Tilt Head** | WidowX WXXMS Turret (`interbotix_ptu`) | 2-DOF Dynamixel head for gaze control |
| **Animated Face** | ESP32 + LCD/LED display (custom firmware) | Expressive eye animations and lip-synced speaking |
| **Microphone Array** | Orbbec stereo mic / XMOS XVF3800 DSP | Audio capture, VAD, and Direction of Arrival |
| **SBC** | Linux PC (Ubuntu 22.04) | Main compute running ROS 2 Humble |

---

## Quick Start

See the full [Workspace Setup Guide](ros2_ws/README.md) for prerequisites and build instructions.

```bash
# Launch the full physical robot
ros2 launch sancho_bringup sancho_full_bringup.launch.py
```

---

## Project Structure

```
sancho_robot/
├── README.md                    ← You are here
├── firmware/                    ← ESP32 face firmware (Arduino)
├── web_ui/                      ← Web frontend
├── ros2_ws/
│   ├── README.md                ← Workspace build guide
│   └── src/
│       ├── sancho_bringup/      ← 🚀 Primary entry point
│       ├── sancho_description/  ← URDF & TF
│       ├── sancho_hardware/     ← Hardware drivers
│       ├── sancho_interfaces/   ← Custom msg/srv/action
│       ├── sancho_perception/   ← Body pose pipeline
│       ├── sancho_vision/       ← Face detection & recognition
│       ├── sancho_audio/        ← Audio & voice assistant
│       ├── sancho_control/      ← Head tracking control
│       ├── sancho_navigation/   ← Nav2 + autonomous navigation
│       ├── sancho_behavior/     ← High-level behavior orchestration
│       ├── sancho_bt_plugins/   ← Nav2 BT plugins (C++)
│       ├── sancho_hri/          ← LLM / STT / TTS gateway
│       ├── sancho_web_bridge/   ← Web bridge & REST API
│       ├── sancho_lifecycle_utils/  ← Lifecycle management utility
│       ├── cliff_detector/      ← Depth-based cliff detection
│       └── third_party_pkgs/    ← Vendored external packages
└── .env                         ← API keys (not committed)
```

---

## License

See [LICENSE](LICENSE).
