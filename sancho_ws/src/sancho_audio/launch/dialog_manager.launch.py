import os
from dotenv import load_dotenv

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, LifecycleNode

# Assuming you also have a TTS_MODELS enum in speech_tools.models
from speech_tools.models import STT_MODELS, TTS_MODELS, TTS_SPEAKERS
from llm_tools.models import PROVIDER, MODELS

load_dotenv()
GOOGLE_STT_API_KEY = os.environ.get("GOOGLE_STT_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')

    vision_pkg_dir = get_package_share_directory('sancho_vision')

    # Microphone
    microphone_node = Node(
        namespace='',
        package='sancho_audio',
        executable='microphone',
        name='microphone',
        output='screen',
        emulate_tty=True
    )

    # Hotword detector
    hotword_node = Node(
        package='sancho_audio',
        executable='hotword_detector_node',
        name='hotword_detector',
        output='screen',
        emulate_tty=True,
        parameters=[
            {'mic_topic': '/sancho_audio/microphone/mono'},
            {'hotword_event_topic': '/voice_events/hotword_detected'}
        ]
    )

    # ----- Speaker Recognition -------
    person_recognition_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(vision_pkg_dir, 'launch', 'body_face_pipeline.launch.py')
        ),
    )

    audio_doa_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_doa_xvf3800_lifecycle',
        name='audio_doa_xvf3800_lifecycle',
    )

    doa_active_speaker = Node(
        package='sancho_audio',
        executable='doa_active_speaker',
        name='doa_active_speaker',
    )
    # ---------------------------------------

    # ------------ Transcription ----------------
    # STT Node
    stt_node = Node(
        package='speech_tools',
        executable='stt',
        name='stt_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            "load_models": f"[['{STT_MODELS.GOOGLE}', '{GOOGLE_STT_API_KEY}']]",
            "active_model": f"{STT_MODELS.GOOGLE}"
        }]
    )

    # VAD Transcriptor
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
    # --------------------------------------

    # LLM Node
    llm_node = Node(
        package='llm_tools',
        executable='llm',
        name='mapirbot',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        parameters=[{
            "llm_load_models": f"[['{PROVIDER.MAPIRBOT}', ['{MODELS.LLM.MAPIRBOT.MAPIRBOT}'], '{OPENAI_API_KEY}']]",
            "llm_active_provider": f"{PROVIDER.MAPIRBOT}",
            "llm_active_model": f"{MODELS.LLM.MAPIRBOT.MAPIRBOT}",
        }]
    )

    # TTS Node
    tts_node = Node(
        package='speech_tools',
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

    # Dialog Manager
    # Core brain that orchestrates nodes and connects to the LLM
    dialog_manager_node = Node(
        package='sancho_audio',
        executable='dialog_manager_node',
        name='dialog_manager',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        parameters=[
            {'hotword_node': 'hotword_detector'},
            {'transcriptor_onde': 'vad_transcriptor'},
            {"mapirbot_url": "https://experiments-suspension-predictions-mid.trycloudflare.com/ask"}
        ]
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',            
        executable='node_configurator',          
        name='node_configurator',
        output='screen',
        emulate_tty=True,
        parameters=[
            {
                'activate': True,
                'node_names': ['microphone', 'audio_doa_xvf3800_lifecycle']
            }
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'prefix',
            default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
            description='Prefijo para lanzar nodos en terminal (p.ej.: “xterm -hold -e”)'
        ),
        person_recognition_launch,
        microphone_node,
        hotword_node,
        audio_doa_node,
        doa_active_speaker,
        stt_node,
        vad_transcriptor_node,
        llm_node,
        tts_node,
        dialog_manager_node,
        configurator_node
    ])