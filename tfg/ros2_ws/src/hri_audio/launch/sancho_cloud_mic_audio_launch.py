from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='hri_audio',
            executable='assistant_helper',
            name='assistant_helper',
            output='screen'
        ),
        Node(
            package='hri_audio',
            executable='assistant',
            name='assistant',
            output='screen'
        ),
        Node(
            package='hri_audio',
            executable='microphone',
            name='microphone',
            output='screen',
        ),
        Node(
            package='sancho_ai',
            executable='sancho_ai',
            name='sancho_ai',
            output='screen'
        ),
        Node(
            package='face_controller',
            executable='face_node',
            name='face_node',
            output='screen'
        ),
    ])