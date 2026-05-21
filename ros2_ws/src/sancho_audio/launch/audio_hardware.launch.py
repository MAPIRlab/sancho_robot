from launch import LaunchDescription
from launch_ros.actions import LifecycleNode, Node

def generate_launch_description():
    audio_gateway_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_gateway',
        name='audio_gateway',
        output='screen',
        emulate_tty=True,
    )

    audio_doa_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_doa_xvf3800_lifecycle',
        name='audio_doa_xvf3800_lifecycle',
        arguments=['--ros-args', '--log-level', 'WARN']
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',
        executable='node_configurator',
        name='node_configurator',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'activate': True,
            'node_names': ['audio_gateway', 'audio_doa_xvf3800_lifecycle']
        }],
    )

    return LaunchDescription([
        audio_gateway_node,
        audio_doa_node,
        configurator_node
    ])