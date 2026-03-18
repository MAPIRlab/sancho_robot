import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # 1. Get paths to the packages
    bringup_dir = get_package_share_directory('sancho_bringup')
    desc_dir = get_package_share_directory('sancho_description')

    # 2. Robot Description (URDF & TF Tree)
    # This launches robot_state_publisher and the joint_state_merger
    description_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(desc_dir, 'launch', 'description.launch.py')
        )
    )

    # 3. Hardware Layer
    sensors_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_dir, 'launch', 'sancho_hardware.launch.py')
        )
    )

    # 4. Processing Layer
    processing_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_dir, 'launch', 'sancho_processing.launch.py')
        )
    )

    return LaunchDescription([
        description_launch,
        sensors_launch,
        processing_launch
    ])