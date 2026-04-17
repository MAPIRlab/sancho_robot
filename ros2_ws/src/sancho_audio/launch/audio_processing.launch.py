import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, LifecycleNode

from sancho_hri.speech.models import TTS_MODELS, TTS_SPEAKERS

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')

    hotword_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='hotword_detector_node',
        name='hotword_detector',
        output='screen',
        emulate_tty=True,
        parameters=[
            {'mic_topic': '/sancho_audio/microphone/mono'},
            {'hotword_event_topic': '/voice_events/hotword_detected'}
        ],
        arguments=['--ros-args', '--log-level', 'WARN']
    )

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

    tts_node = Node(
        package='sancho_hri',
        executable='tts',
        name='tts',
        output='screen',
        emulate_tty=True,
        parameters=[{
            "load_models": f"[['{TTS_MODELS.PIPER}', '']]",
            "active_model": f"{TTS_MODELS.PIPER}",
            "active_speaker": f"{TTS_SPEAKERS.PIPER.DAVEFX}"
        }]
    )

    # Activador para el nodo de audio
    configurator_active = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator_active',
        parameters=[{'activate': True, 'node_names': ['audio_player_lifecycle']}]
    )

    configurator_inactive = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator_inactive',
        parameters=[{'activate': False, 'node_names': ['hotword_detector', 'vad_transcriptor']}]
    )

    return LaunchDescription([
        DeclareLaunchArgument('prefix', default_value='xterm -hold -e' if os.environ.get('DISPLAY') else ''),
        hotword_node,
        doa_active_speaker,
        vad_transcriptor_node,
        audio_player_node,
        tts_node,
        configurator_active,
        configurator_inactive
    ])