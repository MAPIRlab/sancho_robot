#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    # Launch arguments
    use_xterm = LaunchConfiguration("use_xterm")
    prefix_cmd = LaunchConfiguration("prefix")

    # Lifecycle Nodes
    movenet_inference_node = LifecycleNode(
        namespace="",
        package="sancho_perception",
        executable="movenet_inference_node",
        name="movenet_inference_node",
        output="screen",
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    movenet_postprocessing_node = LifecycleNode(
        namespace="",
        package="sancho_perception",
        executable="movenet_postprocessing_node",
        name="movenet_postprocessing_node",
        output="screen",
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    group_detection_node = LifecycleNode(
        namespace="",
        package="sancho_perception",
        executable="group_detection_node",
        name="group_detection_node",
        output="screen",
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    group_waypoint_generator_node = LifecycleNode(
        namespace="",
        package="sancho_perception",
        executable="group_waypoint_generator_node",
        name="group_waypoint_generator_node",
        output="screen",
        prefix=prefix_cmd,
        emulate_tty=True,
    )

    # Lifecycle Manager Node
    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager_perception",
        output="screen",
        parameters=[
            {
                "autostart": True,
                "node_names": [
                    "movenet_inference_node",
                    "movenet_postprocessing_node",
                    "group_detection_node",
                    "group_waypoint_generator_node",
                ],
                "bond_timeout": 0.0,  # Espera 4s para ver si un nodo murió
                "attempt_to_restart": True,  # Reintenta activar si un nodo falla
            }
        ],
    )

    return LaunchDescription(
        [
            # Declare args
            DeclareLaunchArgument(
                "use_xterm",
                default_value="true",
                description="Launch nodes in xterm terminals",
            ),
            DeclareLaunchArgument(
                "prefix",
                default_value="xterm -hold -e" if os.environ.get("DISPLAY") else "",
                description="Command prefix for launching nodes, e.g., xterm -hold -e",
            ),
            GroupAction(
                [
                    movenet_inference_node,
                    movenet_postprocessing_node,
                    group_detection_node,
                    group_waypoint_generator_node,
                    lifecycle_manager,
                ]
            ),
        ]
    )
