import os
from dotenv import load_dotenv
from launch import LaunchDescription
from launch_ros.actions import Node

from speech_tools.models import STT_MODELS, TTS_MODELS, TTS_SPEAKERS
from llm_tools.models import PROVIDER, MODELS

load_dotenv()
GOOGLE_STT_API_KEY = os.environ.get("GOOGLE_STT_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='speech_tools',
            executable='tts',
            name='tts',
            output='screen',
            parameters=[{
                "load_models": f"[['{TTS_MODELS.PIPER}', '']]",
                "active_model": f"{TTS_MODELS.PIPER}",
                "active_speaker": f"{TTS_SPEAKERS.PIPER.SHARVARD}"
            }]
        ),
        Node(
            package='speech_tools',
            executable='stt',
            name='stt',
            output='screen',
            parameters=[{
                "load_models": f"[['{STT_MODELS.WHISPER}', '']]",
                "active_model": f"{STT_MODELS.WHISPER}"
            }]
        ),
        Node(
            package='llm_tools',
            executable='llm',
            name='llm',
            output='screen',
            parameters=[{
                "llm_load_models": f"[['{PROVIDER.GEMINI}', ['{MODELS.LLM.GEMINI.GEMINI_1_5_FLASH}'], '{GEMINI_API_KEY}']]",
                "llm_active_provider": f"{PROVIDER.GEMINI}",
                "llm_active_model": f"{MODELS.LLM.GEMINI.GEMINI_1_5_FLASH}",         
            }]
        ),
    ])