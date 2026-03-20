import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    
    # Asume que guardaste los launch anteriores en sus respectivos paquetes
    audio_pkg_dir = get_package_share_directory('sancho_audio')
    dialog_pkg_dir = get_package_share_directory('sancho_hri')
    behavior_pkg_dir = get_package_share_directory('sancho_behavior')

    hardware_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(audio_pkg_dir, 'launch', 'audio_hardware.launch.py'))
    )

    processing_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(audio_pkg_dir, 'launch', 'audio_processing.launch.py'))
    )

    dialog_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(audio_pkg_dir, 'launch', 'dialog_core.launch.py'))
    )

    behavior_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(behavior_pkg_dir, 'launch', 'attention.launch.py'))
    )

    return LaunchDescription([
        hardware_launch,
        processing_launch,
        behavior_launch,
        dialog_launch
    ])