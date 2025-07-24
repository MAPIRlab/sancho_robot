#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')
    face_node_name = LaunchConfiguration('face_node_name')
    tracker_node_name = LaunchConfiguration('tracker_node_name')

    face_detector_node = LifecycleNode(
        namespace='',
        package='sancho_vision',
        executable='face_detector_lifecycle_node',
        name=face_node_name,
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    face_tracker_node = LifecycleNode(
        namespace='',
        package='sancho_vision',
        executable='face_tracker_lifecycle_node',
        name=tracker_node_name,
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

                'node_names': ['face_detector', 'face_tracker']
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
        DeclareLaunchArgument(
            'face_node_name',
            default_value='face_detector',
            description='Nombre del nodo de detección (face_detector)'
        ),
        DeclareLaunchArgument(
            'tracker_node_name',
            default_value='face_tracker',
            description='Nombre del nodo de seguimiento (face_tracker)'
        ),

        # --------------------
        #  AGRUPO TODOS LOS NODOS
        # --------------------
        GroupAction([
            face_detector_node,
            face_tracker_node,
            configurator_node,
        ]),
    ])
