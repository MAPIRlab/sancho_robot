import os
from dotenv import load_dotenv
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from sancho_hri.speech.models import STT_MODELS, TTS_MODELS, TTS_SPEAKERS
from sancho_hri.llm.models import PROVIDER, MODELS

load_dotenv()
GOOGLE_STT_API_KEY = os.environ.get("GOOGLE_STT_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')

    stt_node = Node(
        package='sancho_hri',
        executable='stt',
        name='stt_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            "load_models": f"[['{STT_MODELS.GOOGLE}', '{GOOGLE_STT_API_KEY}']]",
            "active_model": f"{STT_MODELS.GOOGLE}"
        }]
    )

    llm_node = Node(
        package='sancho_hri',
        executable='llm',
        name='llm_node',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        parameters=[{
            "llm_load_models": f"[['{PROVIDER.OPENAI}', ['{MODELS.LLM.OPENAI.GPT_3_5_TURBO}'], '{OPENAI_API_KEY}']]",
            "llm_active_provider": f"{PROVIDER.OPENAI}",
            "llm_active_model": f"{MODELS.LLM.OPENAI.GPT_3_5_TURBO}",
        }]
    )

    tts_node = Node(
        package='sancho_hri',
        executable='tts',
        name='tts_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            "load_models": f"[['{TTS_MODELS.PIPER}', '']]",
            "active_model": f"{TTS_MODELS.PIPER}",
            "active_speaker": f"{TTS_SPEAKERS.PIPER.DAVEFX}"
        }]
    )

    return LaunchDescription([
        DeclareLaunchArgument('prefix', default_value='xterm -hold -e' if os.environ.get('DISPLAY') else ''),
        stt_node,
        llm_node,
        tts_node
    ])