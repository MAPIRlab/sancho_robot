#   created by: Michael Jonathan (mich1342)
#   github.com/mich1342
#   24/2/2022
#
import os

import launch_ros.actions
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import LaunchConfiguration
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml

from launch import LaunchDescription


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('laser_scan_merger'),
        'config',
        'params.yaml'
    )
    param_substitutions = {
        'flip1': LaunchConfiguration('flip1'),
        'flip2': LaunchConfiguration('flip2'),
        'laser1Alpha': LaunchConfiguration('laser1Alpha'),
        'laser2Alpha': LaunchConfiguration('laser2Alpha'),
        'laser1AngleMin': LaunchConfiguration('laser1AngleMin'),
        'laser1AngleMax': LaunchConfiguration('laser1AngleMax'),
        'laser2AngleMin': LaunchConfiguration('laser2AngleMin'),
        'laser2AngleMax': LaunchConfiguration('laser2AngleMax'),
        'laser1XOff': LaunchConfiguration('laser1XOff'),
        'laser1YOff': LaunchConfiguration('laser1YOff'),
        'laser1ZOff': LaunchConfiguration('laser1ZOff'),
        'laser2XOff': LaunchConfiguration('laser2XOff'),
        'laser2YOff': LaunchConfiguration('laser2YOff'),
        'laser2ZOff': LaunchConfiguration('laser2ZOff'),
        'use_sim_time': LaunchConfiguration('use_sim_time')
    }
    # todo https://github.com/ros-planning/navigation2/blob/6a0c92cad7fb8bb1e3e8500742bc293cddbedc36/nav2_system_tests/src/costmap_filters/test_speed_launch.py#L46-L54

    configured_params = ParameterFile(
        RewrittenYaml(
            source_file=config,
            root_key='',
            param_rewrites=param_substitutions,
            convert_types=True),
        allow_substs=True)

    laser_scan_merger_node = launch_ros.actions.Node(
        package='laser_scan_merger',
        executable='laser_scan_merger',
        parameters=[configured_params],
        output='screen',
        respawn=True,
        respawn_delay=2,
    )

    pointcloud_to_laserscan = launch_ros.actions.Node(
        name='pointcloud_to_laserscan',
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        parameters=[config]
    )

    return LaunchDescription([
        # launch_ros.actions.SetParameter(name='laser1XOff', value=laser1x_off),
        laser_scan_merger_node,
        pointcloud_to_laserscan
    ])