import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='interbotix_xs_sdk',
            executable='xs_sdk',
            name='interbotix_xs_sdk',
            output='screen',
            namespace='wxxms',
            prefix="xterm -hold -e",
            parameters=[{
                'motor_configs': os.path.join(get_package_share_directory("interbotix_xsturret_control"), 'config', 'wxxms.yaml'),
                'mode_configs': os.path.join(get_package_share_directory("interbotix_xsturret_control"), 'config', 'modes.yaml'),
                'load_configs': False
            }]
        ),
        Node(
            package='sancho_head_control',
            executable='head_controller_node',
            name='head_controller_node',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
    ])