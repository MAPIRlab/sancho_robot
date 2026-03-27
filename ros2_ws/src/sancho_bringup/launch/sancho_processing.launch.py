from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='laser_scan_merger',
            executable='laser_scan_merger',
            name='laser_scan_merger',
            output='screen',
            parameters=[{
                'scanTopic1': '/scan_1st',
                'scanTopic2': '/scan_2nd',
                'target_frame': 'base_link',
                'laser1_frame': 'laser_front',
                'laser2_frame': 'laser_back',
                'pointCloudTopic':  '/laser_cloud',
                'pointCloudFrameId': 'base_link',
            }]
        ),
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='cloud_to_scan',
            output='screen',
            remappings=[('cloud_in', '/laser_cloud'), ('scan', '/scan_merged')],
            parameters=[{
                'target_frame': 'base_link',
                'range_max': 30.0,
                'use_inf': True
            }]
        )
    ])