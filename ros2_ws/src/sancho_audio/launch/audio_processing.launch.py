import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, LifecycleNode

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')


    doa_active_speaker = Node(
        package='sancho_audio',
        executable='doa_active_speaker',
        name='doa_active_speaker',
    )

    vad_transcriptor_node = Node(
        package='sancho_audio',
        executable='vad_transcriptor_node',
        name='vad_transcriptor',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        parameters=[
            {'mic_topic': '/sancho_audio/microphone/mono'},
            {'transcription_topic': '/voice_events/user_transcription'},
            {'vad_criterion': 'silero'},
            {"intensity_threshold": 900},
            {'timeout_seconds': 5.0},
            {"chunk_size": 0.5},
            {"silence_patience_seconds": 1.5}
        ]
    )

    audio_player_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_player',
        name='audio_player_lifecycle',
        output='screen'
    )

    # Activador para el nodo de audio
    configurator_active = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator_active',
        parameters=[{'activate': True, 'node_names': ['audio_player_lifecycle']}]
    )

    return LaunchDescription([
        DeclareLaunchArgument('prefix', default_value='xterm -hold -e' if os.environ.get('DISPLAY') else ''),

        doa_active_speaker,
        vad_transcriptor_node,
        audio_player_node,
        configurator_active
    ])