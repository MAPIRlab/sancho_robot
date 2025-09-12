#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')
    face_node_name = LaunchConfiguration('face_node_name')
    face_recognizer_node_name = LaunchConfiguration('face_recognizer_node_name')

    face_detector_node = LifecycleNode(
        namespace='',
        package='sancho_vision',
        executable='human_face_detector_lifecycle',
        name=face_node_name,
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    face_recognizer_node = LifecycleNode(
        namespace='',
        package='sancho_vision',
        executable='human_face_recognizer_lifecycle',
        name=face_recognizer_node_name,
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
                'activate': True,
                'node_names': ['face_detector', 'face_recognizer']
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
            'face_recognizer_node_name',
            default_value='face_recognizer',
            description='Nombre del nodo de seguimiento (face_recognizer)'
        ),

        # --------------------
        #  AGRUPO TODOS LOS NODOS
        # --------------------
        GroupAction([
            face_detector_node,
            face_recognizer_node,
            configurator_node,
        ]),
    ])
