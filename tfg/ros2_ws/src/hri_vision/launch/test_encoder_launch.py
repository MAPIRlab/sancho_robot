from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='hri_vision',
            executable='detector',
            name='detector',
            output='screen'
        ),
        Node(
            package='ros2web',
            executable='server',
            name='r2w_server',
            output='screen'
        )
    ])
