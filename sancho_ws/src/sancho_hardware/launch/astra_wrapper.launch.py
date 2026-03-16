import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch_ros.actions import PushRosNamespace
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    astra_camera_path = get_package_share_directory('astra_camera')
    
    return LaunchDescription([
        GroupAction([
            PushRosNamespace('astra_camera'),
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(
                    os.path.join(astra_camera_path, 'launch', 'astra.launch.xml')
                ),
                launch_arguments={
                    'serial_number': "'20070830098'",
                    'camera_name': 'camera',
                    'color_fps': '15',
                    'depth_fps': '15',
                    'ir_fps': '15'
                }.items()
            )
        ])
    ])