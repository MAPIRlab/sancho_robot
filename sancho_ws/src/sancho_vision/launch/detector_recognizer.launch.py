#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node
from launch.substitutions import PythonExpression

from sancho_web_assistant.apis import API_LIST


def generate_launch_description():
    prefix_cmd = LaunchConfiguration('prefix')
    face_node_name = LaunchConfiguration('face_node_name')
    face_recognizer_node_name = LaunchConfiguration('face_recognizer_node_name')
    face_manager_node_name = LaunchConfiguration('face_manager_node_name')
    activate_arg = LaunchConfiguration('activate')

    activate_bool = PythonExpression(
        ["'", activate_arg, "' == 'true'"]
    )

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

    face_manager_node = LifecycleNode(
        namespace='',
        package='sancho_vision',
        executable='human_face_manager_lifecycle',
        name=face_manager_node_name,
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    configurator_node = Node(
        package='sancho_lifecycle_utils',
        executable='node_configurator',
        name='node_configurator',
        output='screen',
        parameters=[{
            'activate': activate_bool,   # <- ahora viene del argumento del launch
            'node_names': ['face_detector', 'face_recognizer', 'face_manager']
        }],
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
        DeclareLaunchArgument(
            'face_manager_node_name',
            default_value='face_manager',
            description='Nombre del nodo de gestión de caras (face_manager)'
        ),
        DeclareLaunchArgument(
            'activate',
            default_value='true',
            choices=['true', 'false'],
            description='Si "true", node_configurator activará los nodos lifecycle automáticamente'
        ),

        Node(
            package='sancho_vision',
            executable='gui',
            name='hri_gui',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),

        Node(
            package='rumi_web',
            executable='session_manager',
            name='session_manager',
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),

        Node(
            package='sancho_web_assistant',
            executable='api_rest',
            name='api_rest',
            parameters=[{
                "apis": f"['{API_LIST.FACEPRINTS}', '{API_LIST.SESSIONS}']"
            }],
            output='screen',
            prefix="xterm -hold -e",
            emulate_tty=True,
        ),

        # --------------------
        #  AGRUPO TODOS LOS NODOS
        # --------------------
        GroupAction([
            face_detector_node,
            face_recognizer_node,
            face_manager_node,
            configurator_node,
        ]),
    ])
