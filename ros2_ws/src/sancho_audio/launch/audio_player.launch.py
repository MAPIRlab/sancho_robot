#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    # Parámetros de lanzamiento
    prefix_cmd = LaunchConfiguration('prefix')
    audio_node_name = 'audio_player'

    # Nodos lifecycle
    audio_player_node = LifecycleNode(
        namespace='',
        package='sancho_audio',
        executable='audio_player',
        name=audio_node_name,
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )
    microphone_publisher_node = Node(
        namespace='',
        package='sancho_audio',
        executable='microphone_capturer',
        name='microphone_publisher',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )
    vad_node = Node(
        namespace='',
        package='sancho_audio',
        executable='voice_activity_detector',
        name='vad_node',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )
    sound_direction_node = Node(
        namespace='',
        package='sancho_audio',
        executable='audio_direction',
        name='sound_direction_node',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',
        executable='node_configurator',
        name='node_configurator',
        output='screen',
        parameters=[
            {
                'node_names': [
                    audio_node_name,
                ]
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'prefix',
                default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
                description='Prefijo para lanzar nodos en terminal',
            ),
            GroupAction(
                [
                    audio_player_node,
                    microphone_publisher_node,
                    vad_node,
                    sound_direction_node,
                    configurator_node,
                ]
            ),
        ]
    )
