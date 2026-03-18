import os

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # 1. The C++ face node that communicates with the hardware
        Node(
            package='sancho_hardware',
            executable='face_node',
            name='face_node',
            output='screen',
        ),
        # 2. The interactive python script that publishes emotions
        Node(
            package='sancho_hardware',
            executable='test_face_emotions',
            name='test_face_emotions',
            output='screen',
            # Run the interactive script in a new terminal window
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
    ])
