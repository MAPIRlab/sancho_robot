[← Back to Main README](../../../README.md)

# 🚀 sancho_bringup

> **This is the primary entry point for the Sancho robot.**

The `sancho_bringup` package provides the top-level orchestrated launch files that initialize the robot's physical description (URDF), hardware drivers, and essential sensor data processing. It does not contain functional nodes itself — it composes subsystems from other packages.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `sancho_full_bringup.launch.py` | **Top-level launcher.** Sequentially brings up: (1) robot description, (2) hardware drivers, (3) processing layer. |
| `sancho_hardware.launch.py` | Launches all hardware drivers from `sancho_hardware`: base chassis, front/rear LiDARs, Astra RGB-D camera, nose camera, head servos. |
| `sancho_processing.launch.py` | Launches scan fusion nodes: `laser_scan_merger` + `pointcloud_to_laserscan`. |

### Usage

```bash
# Full robot bringup (description + hardware + processing)
ros2 launch sancho_bringup sancho_full_bringup.launch.py
```

---

## ROS 2 API

*The following API is established by `sancho_processing.launch.py`.*

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/scan_1st` | `sensor_msgs/msg/LaserScan` | Raw front LiDAR scan |
| `/scan_2nd` | `sensor_msgs/msg/LaserScan` | Raw rear LiDAR scan |
| `/laser_cloud` | `sensor_msgs/msg/PointCloud2` | Intermediate merged 3D cloud |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/laser_cloud` | `sensor_msgs/msg/PointCloud2` | Merged 3D point cloud from both LiDARs |
| `/scan_merged` | `sensor_msgs/msg/LaserScan` | Unified 360° 2D scan (max range: 30 m) |

---

## Dependencies

- **Internal:** `sancho_description`, `sancho_hardware`
- **External:** `robot_state_publisher`, `pointcloud_to_laserscan`, `laser_scan_merger`
