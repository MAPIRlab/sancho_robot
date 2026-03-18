import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    urg_node2_path = get_package_share_directory('urg_node2')
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(urg_node2_path, 'launch', 'urg_node2_2lidar.launch.py')
            ),
            launch_arguments={'range_min': '0.05'}.items()
        )
    ])