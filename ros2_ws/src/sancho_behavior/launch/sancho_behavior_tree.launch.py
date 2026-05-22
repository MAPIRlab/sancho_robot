import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')
    audio_pkg_dir = get_package_share_directory('sancho_audio')

    hardware_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(audio_pkg_dir, 'launch', 'audio_hardware.launch.py'))
    )

    processing_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(audio_pkg_dir, 'launch', 'audio_processing.launch.py'))
    )

    dialog_core_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(audio_pkg_dir, 'launch', 'dialog_core.launch.py'))
    )

    head_action_server = Node(
        package='sancho_control',
        executable='head_action_server',
        name='head_action_server',
        output='screen',
        emulate_tty=True
    )

    turn_action_server = Node(
        package='sancho_control',
        executable='turn_action_server',
        name='turn_action_server',
        output='screen',
        emulate_tty=True
    )

    tracking_node = Node(
        package='sancho_control',
        executable='head_control_face_tracker',
        name='face_tracker',
        output='screen',
        emulate_tty=True
    )

    central_face_cluster_service = Node(
        package='sancho_vision',
        executable='central_faces_cluster_node',
        name='central_faces_cluster_node',
        output='screen',
        emulate_tty=True,
        arguments=['--ros-args', '--log-level', 'WARN']
    )

    sancho_ai_node = Node(
        package='sancho_hri',
        executable='sancho_ai',
        name='sancho_ai',
        output='screen',
        emulate_tty=True,
        prefix='xterm -hold -e'
    )

    behavior_tree = Node(
        package='sancho_behavior',
        executable='sancho_behavior_tree',
        name='sancho_behavior_tree',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True
    )

    configurator_inactive = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator_inactive',
        parameters=[{'activate': False, 'node_names': ['face_tracker']}]
    )

    return LaunchDescription([
        DeclareLaunchArgument('prefix', default_value='xterm -hold -e' if os.environ.get('DISPLAY') else ''),
        hardware_launch,
        processing_launch,
        dialog_core_launch,
        head_action_server,
        turn_action_server,
        tracking_node,
        central_face_cluster_service,
        sancho_ai_node,
        behavior_tree,
        configurator_inactive
    ])