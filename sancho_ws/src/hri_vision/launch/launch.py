from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='hri_vision',
            executable='camera',
            name='camera',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
        Node(
            package='hri_vision',
            executable='detector',
            name='detector',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
        Node(
            package='hri_vision',
            executable='recognizer',
            name='recognizer',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
        Node(
            package='hri_vision',
            executable='logic',
            name='logic',
            output='screen',
        )
    ])