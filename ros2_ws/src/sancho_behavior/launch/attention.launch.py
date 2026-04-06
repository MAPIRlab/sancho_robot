import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, LifecycleNode

def generate_launch_description():
    vision_pkg_dir = get_package_share_directory('sancho_vision')

    person_recognition_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(vision_pkg_dir, 'launch', 'identification.launch.py')
        ),
    )

    faces_cluster_node = Node(
        package='sancho_vision',
        executable='central_faces_cluster_node',
        name='central_faces_cluster_node',
        output='screen',
        arguments=['--ros-args', '--log-level', 'WARN']
    )

    face_tracker_node = LifecycleNode(
        namespace='',
        package='sancho_control',
        executable='head_control_face_tracker',
        name='face_tracker_lifecycle',
        output='screen'
    )

    attention_manager_node = Node(
        package='sancho_behavior',
        executable='attention_manager_node',
        name='attention_manager',
        output='screen'
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='tracker_configurator',
        parameters=[{'activate': False, 'node_names': ['face_tracker_lifecycle']}]
    )

    return LaunchDescription([
        person_recognition_launch,
        faces_cluster_node,
        face_tracker_node,
        attention_manager_node,
        configurator_node
    ])