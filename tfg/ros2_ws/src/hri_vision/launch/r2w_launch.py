from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='ros2web',
            executable='server',
            name='server',
            parameters=[{
                'topics': "[['/camera/color/recognition', 'IMAGE'], ['/logic/info/actual_people', 'ACTUAL_PEOPLE']]"
            }],
            output='screen'
        )
    ])
