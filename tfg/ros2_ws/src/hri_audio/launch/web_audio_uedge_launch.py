from launch import LaunchDescription
from launch_ros.actions import Node

from speech_tools.models import STT_MODELS, TTS_MODELS, TTS_SPEAKERS
from llm_tools.models import PROVIDER, MODELS
from sancho_web_assistant.apis import API_LIST


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
                "active_speaker": f"{TTS_SPEAKERS.PIPER.DAVEFX}"
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
                "llm_load_models": f"[['{PROVIDER.QWEN}', ['{MODELS.LLM.QWEN.QWEN_2_5_14B_IT}'], '']]",
                "llm_active_provider": f"{PROVIDER.QWEN}",
                "llm_active_model": f"{MODELS.LLM.QWEN.QWEN_2_5_14B_IT}",
            }]
        ),
    ])