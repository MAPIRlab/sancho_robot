#!/usr/bin/env python3
"""
Pipeline B launch file — Body-anchored Face Recognition.

Replaces Pipeline A's (HumanFaceDetector + HumanFaceRecognizer) with:

  Camera ──► sancho_tracking_node (YOLOX + ByteTrack)
                  │  /sancho_perception/human_tracking
                  ▼
             BodyFaceFusionNode  (detect + align + encode + classify)
                  │  /face_recognitions
                  ├──► FaceVisualizerNode  → /face_recognitions/visual
                  └──► HumanFaceManagerLifecycle (HRI: greet, ask name, TTS…)

Nodes that are NOT started (Pipeline A only):
  - human_face_detector_lifecycle
  - human_face_recognizer_lifecycle

The face_manager and GUI are kept because they subscribe to /face_recognitions,
which is the same topic published by BodyFaceFusionNode.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node

from sancho_web_bridge.assistant.apis import API_LIST


def generate_launch_description():
    prefix_cmd        = LaunchConfiguration('prefix')
    face_manager_name = LaunchConfiguration('face_manager_node_name')

    # ──────────────────────────────────────────────────────────────────────────
    #  Body Tracker  (YOLOX person detector + ByteTracker)
    #  Publishes: /sancho_perception/human_tracking (FaceDetectionArray with body boxes)
    # ──────────────────────────────────────────────────────────────────────────
    body_tracker_node = Node(
        package='sancho_perception',
        executable='perception_test',    # registered name in sancho_perception/setup.py
        name='sancho_tracking_node',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        # Remap if the camera publishes image_raw instead of image_rect
        # remappings=[('/sancho_camera/image_rect', '/sancho_camera/image_raw')],
    )

    # ──────────────────────────────────────────────────────────────────────────
    #  Body-Face Fusion  (Pipeline B core)
    #  Subscribes: /sancho_perception/human_tracking
    #  Publishes:  /face_recognitions  (drop-in replacement for Pipeline A)
    # ──────────────────────────────────────────────────────────────────────────
    fusion_node = Node(
        package='sancho_vision',
        executable='body_face_fusion_node',
        name='body_face_fusion',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        parameters=[{
            'human_tracking_topic':    '/sancho_perception/human_tracking',
            'face_recognitions_topic': '/face_recognitions',
            'detector_name':           'mtcnn',  # swap to 'yolov8' or 'mtcnn' for better recall
            'encoder_name':            'efficientface',
            'head_fraction':           0.60,
            'cache_ttl':               10.0,
            'cache_max_size':          20,
            'cleanup_timeout':         30.0,
        }],
    )

    # ──────────────────────────────────────────────────────────────────────────
    #  Face Visualizer  (optional, draws bounding boxes + names)
    #  Subscribes: /face_recognitions
    #  Publishes:  /face_recognitions/visual
    # ──────────────────────────────────────────────────────────────────────────
    visualizer_node = Node(
        package='sancho_vision',
        executable='face_visualizer_node',
        name='face_visualizer',
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
        parameters=[{
            'face_recognitions_topic': '/face_recognitions',
            'output_image_topic':      '/face_recognitions/visual',
            'middle_bound':            0.75,
            'upper_bound':             0.85,
            'show_distance':           True,
            'show_score':              True,
            'draw_rectangle':          True,
        }],
    )

    # ──────────────────────────────────────────────────────────────────────────
    #  Face Manager  (HRI logic: greet, ask name, TTS…)
    #  Subscribes: /face_recognitions  ← same topic fusion node publishes to
    #  Note: This is a lifecycle node, managed by the auto-activator below.
    # ──────────────────────────────────────────────────────────────────────────
    face_manager_node = LifecycleNode(
        namespace='',
        package='sancho_vision',
        executable='human_face_manager_lifecycle',
        name=face_manager_name,
        output='screen',
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    # Automatically configure + activate the face_manager lifecycle node
    auto_activator_node = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='node_auto_activator_face',
        output='screen',
        parameters=[{
            'autostart':           True,
            'node_names':          ['face_manager'],
            'bond_timeout':        0.0,
            'attempt_to_restart':  True,
        }],
    )

    # ──────────────────────────────────────────────────────────────────────────
    #  GUI
    # ──────────────────────────────────────────────────────────────────────────
    gui_node = Node(
        package='sancho_vision',
        executable='gui',
        name='hri_gui',
        output='screen',
        prefix='xterm -hold -e',
        emulate_tty=True,
    )

    # ──────────────────────────────────────────────────────────────────────────
    #  REST API (for faceprint database management via web UI)
    # ──────────────────────────────────────────────────────────────────────────
    api_rest_node = Node(
        package='sancho_web_bridge',
        executable='api_rest',
        name='api_rest',
        parameters=[{
            'apis': f"['{API_LIST.FACEPRINTS}', '{API_LIST.SESSIONS}', "
                    f"'{API_LIST.MEMORIES}', '{API_LIST.STT_MODELS}', "
                    f"'{API_LIST.TTS_MODELS}', '{API_LIST.LLM_MODELS}']"
        }],
        output='screen',
        prefix='xterm -hold -e',
        emulate_tty=True,
    )

    return LaunchDescription([
        # ── Arguments ─────────────────────────────────────────────────────────
        DeclareLaunchArgument(
            'prefix',
            default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
            description='Prefix to launch nodes in a terminal window, e.g.: "xterm -hold -e"'
        ),
        DeclareLaunchArgument(
            'face_manager_node_name',
            default_value='face_manager',
            description='ROS node name for the face manager lifecycle node'
        ),

        # ── Nodes ──────────────────────────────────────────────────────────────
        auto_activator_node,
        GroupAction([
            body_tracker_node,
            fusion_node,
            visualizer_node,
            face_manager_node,
            gui_node,
            api_rest_node,
        ]),
    ])
