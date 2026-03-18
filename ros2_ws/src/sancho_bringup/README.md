# sancho_bringup

**Role:** The `sancho_bringup` package is the primary entry point for starting up the physical layer of the Sancho robot. Rather than containing functional C++ or Python nodes itself, it provides the high-level orchestrated launch files required to initialize the robot's physical description (URDF), instantiate the hardware abstraction interfaces, and begin essential early-pipeline sensor data processing.

## Core Launch Files

### `sancho_full_bringup.launch.py`
- **Specific Function:** The top-level launch file. Executing this file will sequentially bring up every essential component of the physical robot layer in the correct order:
   1. The `sancho_description` launch (robot_state_publisher and URDF).
   2. The hardware sensor and actuator drivers (`sancho_hardware.launch.py`).
   3. The raw sensor data processing (`sancho_processing.launch.py`).

### `sancho_hardware.launch.py`
- **Specific Function:** A centralized launch file for the entire `sancho_hardware` package. It iterates through and includes the specific wrapper launch files for the robot's hardware components:
   - Base Ranger (Chassis controller)
   - Front and Back LiDARs
   - Orbbec Astra 3D Camera
   - Nose Camera
   - Head servos

### `sancho_processing.launch.py`
- **Specific Function:** Launches nodes responsible for the lowest level of sensor data fusion before it hits the navigation or perception stacks. 
- **Key Nodes Launched:**
   - `laser_scan_merger`: Takes the individual scans from the front (`/scan_1st`) and rear (`/scan_2nd`) LiDAR units and combines them into a single 3D pointcloud (`/laser_cloud`) positioned in the `base_link` frame.
   - `pointcloud_to_laserscan_node` (named `cloud_to_scan`): Projects the merged 3D pointcloud back down into a comprehensive, unified 2D planar laser scan (`/scan_merged`). This unified scan provides a full 360-degree view around the robot's base and is essential for Nav2 obstacle avoidance.

---

## API (Topics/Services)

*Note: As `sancho_bringup` is purely a launch directory, the following represents the topics established by its `sancho_processing.launch.py` script.*

### Subscribed Topics
- `/scan_1st` (`sensor_msgs/msg/LaserScan`): Raw data from the front LiDAR.
- `/scan_2nd` (`sensor_msgs/msg/LaserScan`): Raw data from the rear LiDAR.
- `/laser_cloud` (`sensor_msgs/msg/PointCloud2`): The intermediate merged 3D cloud.

### Published Topics
- `/laser_cloud` (`sensor_msgs/msg/PointCloud2`): The output of the `laser_scan_merger`.
- `/scan_merged` (`sensor_msgs/msg/LaserScan`): The final output 360-degree 2D scan produced by `pointcloud_to_laserscan`, with a maximum range parameter set to 30.0 meters.
