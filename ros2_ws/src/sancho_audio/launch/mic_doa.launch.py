import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')

    audio_gateway_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_gateway',
        name='audio_gateway',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    face_node = Node(
        namespace='',
        package='sancho_hardware',
        executable='face_node',
        name='face_node',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    audio_doa_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_doa_xvf3800_lifecycle',
        name='audio_doa_xvf3800_lifecycle',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )


    doa_active_speaker_node = Node(
        namespace='',
        package='sancho_audio',
        executable='doa_active_speaker',
        name='doa_active_speaker'
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator',
        output='screen',
        parameters=[
            {
                'activate': True,
                'node_names': ['audio_gateway', 'audio_doa_xvf3800_lifecycle'] # audio_doa_lifecycle
            }
        ],
    )

    return LaunchDescription([
        # -------------------
        #  DECLARO ARGUMENTOS
        # -------------------
        DeclareLaunchArgument(
            'prefix',
            default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
            description='Prefijo para lanzar nodos en terminal (p.ej.: “xterm -hold -e”)'
        ),

        # --------------------
        #  AGRUPO TODOS LOS NODOS
        # --------------------
        GroupAction([
            audio_gateway_node,
            face_node,
            audio_doa_node,
            doa_active_speaker_node,
            configurator_node
        ]),
    ])
