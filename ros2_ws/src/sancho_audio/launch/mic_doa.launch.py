import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')

    microphone_node = Node(
        namespace='',
        package='sancho_audio',
        executable='microphone',
        name='microphone',
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

    # audio_doa_node = LifecycleNode(
    #     namespace='',
    #     package='sancho_audio',
    #     executable='audio_doa_lifecycle',
    #     name='audio_doa_lifecycle',
    #     output='screen',
    #     prefix=prefix_cmd,
    #     emulate_tty=True,
    # )


    audio_doa_overlay_node = Node(
        namespace='',
        package='sancho_audio',
        executable='audio_doa_overlay',
        name='audio_doa_overlay'
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator',
        output='screen',
        parameters=[
            {
                'activate': True,
                'node_names': ['microphone', 'audio_doa_lifecycle'] # audio_doa_xvf3800_lifecycle
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
            microphone_node,
            face_node,
            audio_doa_node,
            audio_doa_overlay_node,
            configurator_node
        ]),
    ])
