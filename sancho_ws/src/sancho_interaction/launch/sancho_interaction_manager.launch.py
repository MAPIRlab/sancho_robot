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
    manager_node_name = 'interaction_manager'

    # Nodos lifecycle
    interaction_manager_node = LifecycleNode(
        namespace='',
        package='sancho_interaction',
        executable='interaction_manager_node',
        name=manager_node_name,
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )
    # Comandos para configurar los nodos
    configurator_node = Node(
        package='sancho_lifecycle_utils',
        executable='node_configurator',
        name='node_configurator',
        output='screen',
        parameters=[
            {
                'node_names': [manager_node_name]
            }
        ],
    )


    return LaunchDescription([
        DeclareLaunchArgument(
            'prefix',
            default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
            description='Prefijo para lanzar nodos en terminal'
        ),

        GroupAction([
            interaction_manager_node,
            configurator_node
        ]),
    ])
