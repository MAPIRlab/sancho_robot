#!/usr/bin/env python3
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode, Node


def generate_launch_description():
    # Paths
    sancho_perception_dir = get_package_share_directory('sancho_perception')
    movenet_params_file = os.path.join(sancho_perception_dir, 'config', 'movenet_inference_params.yaml')
    postprocessing_params_file = os.path.join(sancho_perception_dir, 'config', 'movenet_postprocessing_params.yaml')

    # Launch Arguments
    use_xterm = LaunchConfiguration('use_xterm')
    prefix_cmd = LaunchConfiguration('prefix')

    # Lifecycle Nodes
    movenet_inference_node = LifecycleNode(
        namespace='',  
        package='sancho_perception',
        executable='movenet_inference_node',
        name='movenet_inference_node',
        output='screen',
        # parameters=[movenet_params_file],
        prefix='xterm -hold -e',
        emulate_tty=True,
    )
    
    movenet_postprocessing_node = LifecycleNode(
        namespace='',  
        package='sancho_perception',
        executable='movenet_postprocessing_node',
        name='movenet_postprocessing_node',
        output='screen',
        # parameters=[postprocessing_params_file],
        prefix='xterm -hold -e',
        emulate_tty=True,
    )

    # Lifecycle Manager
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_perception',
        output='screen',
        parameters=[{
            'autostart': True,
            'node_names': [
                'movenet_inference_node',
                'movenet_postprocessing_node'
            ],
            'bond_timeout': 0.0  

        }]
    )

    return LaunchDescription([
        # Declare arguments
        DeclareLaunchArgument(
            'use_xterm',
            default_value='true',
            description='Launch nodes in xterm terminals'
        ),
        DeclareLaunchArgument(
            'prefix',
            default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
            description='Command prefix for launching nodes, e.g., xterm -hold -e'
        ),
        
        GroupAction([
            movenet_inference_node,
            movenet_postprocessing_node,
            lifecycle_manager,
        ]),
    ])
