import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    
    audio_pkg_dir = get_package_share_directory('sancho_audio')
    behavior_pkg_dir = get_package_share_directory('sancho_behavior')

    launch_attention_arg = DeclareLaunchArgument(
        'launch_attention_stack',
        default_value='true',
        description='Launch attention stack required by L2 preemption handshake',
    )

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
        PythonLaunchDescriptionSource(
            os.path.join(behavior_pkg_dir, 'launch', 'attention.launch.py')
        ),
        condition=IfCondition(LaunchConfiguration('launch_attention_stack')),
    )

    bt_node = Node(
        package='sancho_behavior',
        executable='sancho_behavior_tree',
        name='sancho_behavior_tree',
        output='screen'
    )

    return LaunchDescription([
        launch_attention_arg,
        hardware_launch,
        processing_launch,
        behavior_launch,
        dialog_launch,
        bt_node
    ])