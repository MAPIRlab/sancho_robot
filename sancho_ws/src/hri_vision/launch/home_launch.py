from launch import LaunchDescription
from launch_ros.actions import Node

from sancho_web_assistant.apis import API_LIST


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='hri_vision',
            executable='video',
            name='video',
            output='screen'
        ),
        Node(
            package='hri_vision',
            executable='detector',
            name='detector',
            output='screen'
        ),
        Node(
            package='hri_vision',
            executable='recognizer',
            name='recognizer',
            output='screen'
        ),
        Node(
            package='hri_vision',
            executable='logic',
            name='logic',
            output='screen',
        ),
        Node(
            package='hri_vision',
            executable='gui',
            name='gui',
            output='screen',
        ),
        Node(
            package='ros2web',
            executable='server',
            name='r2w_server',
            parameters=[{
                'topics': "[['/camera/color/recognition', 'IMAGE'], ['/logic/info/actual_people', 'ACTUAL_PEOPLE']]"
            }],
            output='screen'
        ),
        Node(
            package='sancho_web_assistant',
            executable='sancho_web_assistant',
            name='sancho_web_assistant',
            output='screen'
        ),
        Node(
            package='sancho_web_assistant',
            executable='api_rest',
            name='api_rest',
            output='screen',
            parameters=[{
                "apis": f"['{API_LIST.FACEPRINTS}', '{API_LIST.SESSIONS}', '{API_LIST.LLM_MODELS}', '{API_LIST.LOGS}']"
            }]
        ),
        Node(
            package='sancho_web_assistant',
            executable='database_manager',
            name='database_manager',
            output='screen'
        ),
        Node(
            package='llm_tools',
            executable='llm',
            name='llm',
            output='screen'
        ),
        Node(
            package='sancho_ai',
            executable='sancho_ai',
            name='sancho_ai',
            output='screen'
        ),
        Node(
            package='rumi_web',
            executable='session_manager',
            name='session_manager',
            output='screen'
        ),
    ])