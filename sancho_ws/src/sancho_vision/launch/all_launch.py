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
        ),
        Node(
            package='ros2web',
            executable='server',
            name='r2w_server',
            parameters=[{
                'topics': "[['/camera/color/recognition', 'IMAGE'], ['/logic/info/actual_people', 'ACTUAL_PEOPLE']]"
            }],
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
        Node(
            package='sancho_web_assistant',
            executable='sancho_web_assistant',
            name='sancho_web_assistant',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
        Node(
            package='sancho_web_assistant',
            executable='faceprint_api',
            name='faceprint_api',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
        Node(
            package='sancho_ai',
            executable='sancho_ai',
            name='sancho_ai',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),
    ])