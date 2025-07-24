from launch import LaunchDescription
from launch_ros.actions import Node

from sancho_web_assistant.apis import API_LIST


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='hri_audio',
            executable='audio',
            name='audio',
            output='screen',
        ),
        Node( # Revisar, porque tiene el picovoice porcupine, depende de su eficiencia (es mas mandar audio por red o el modelo?)
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
            package='sancho_ai',
            executable='sancho_ai',
            name='sancho_ai',
            output='screen'
        ),
        Node(
            package='ros2web',
            executable='server',
            name='r2w_server',
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
                "apis": f"['{API_LIST.TTS_MODELS}', '{API_LIST.STT_MODELS}', '{API_LIST.LLM_MODELS}']"
            }]
        ),
    ])