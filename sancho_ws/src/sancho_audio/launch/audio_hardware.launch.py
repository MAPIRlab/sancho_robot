from launch import LaunchDescription
from launch_ros.actions import Node, LifecycleNode

def generate_launch_description():
    microphone_node = Node(
        namespace='',
        package='sancho_audio',
        executable='microphone',
        name='microphone',
        output='screen',
        emulate_tty=True
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
            'node_names': ['microphone', 'audio_doa_xvf3800_lifecycle']
        }],
    )

    return LaunchDescription([
        microphone_node,
        audio_doa_node,
        configurator_node
    ])