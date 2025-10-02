import os
from dotenv import load_dotenv

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node

from sancho_web_assistant.apis import API_LIST
from speech_tools.models import STT_MODELS, TTS_MODELS, TTS_SPEAKERS
from llm_tools.models import PROVIDER, MODELS

load_dotenv()
GOOGLE_STT_API_KEY = os.environ.get("GOOGLE_STT_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')

    llm = Node(
        package='llm_tools',
        executable='llm',
        name='llm',
        parameters=[{
            "llm_load_models": f"[['{PROVIDER.GEMINI}', ['{MODELS.LLM.GEMINI.GEMINI_2_5_FLASH}'], '{GEMINI_API_KEY}']]",
            "llm_active_provider": f"{PROVIDER.GEMINI}",
            "llm_active_model": f"{MODELS.LLM.GEMINI.GEMINI_2_5_FLASH}",         
            #"embedding_load_models": f"[['{PROVIDER.GEMINI}', ['{MODELS.LLM.GEMINI.GEMINI_2_5_FLASH}'], '{GEMINI_API_KEY}']]",
            #"embedding_active_provider": f"{PROVIDER.GEMINI}",
            #"embedding_active_model": f"{MODELS.LLM.GEMINI.GEMINI_2_5_FLASH}",
        }]
    )

    tts = Node(
        package='speech_tools',
        executable='tts',
        name='tts',
        parameters=[{
            "load_models": f"[['{TTS_MODELS.PIPER}', '']]",
            "active_model": f"{TTS_MODELS.PIPER}",
            "active_speaker": f"{TTS_SPEAKERS.PIPER.DAVEFX}"
        }]
    )

    stt = Node(
        package='speech_tools',
        executable='stt',
        name='stt',
        parameters=[{
            "load_models": f"[['{STT_MODELS.GOOGLE}', '{GOOGLE_STT_API_KEY}']]",
            "active_model": f"{STT_MODELS.GOOGLE}"
        }]
    )

    assistant_helper = Node(
        package='sancho_audio',            
        executable='assistant_helper',          
        name='assistant_helper',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    assistant = Node(
        package='sancho_audio',            
        executable='assistant',          
        name='assistant',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    sancho_ai = Node(
        package='sancho_ai',
        executable='sancho_ai',          
        name='sancho_ai',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    database_manager = Node(
        package='sancho_web_assistant',
        executable='database_manager',          
        name='database_manager',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
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
            llm,
            tts,
            stt,
            assistant_helper,
            assistant,
            sancho_ai,
            database_manager
        ]),
    ])
