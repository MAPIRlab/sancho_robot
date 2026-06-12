import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import SetRemap

def generate_launch_description():
    return LaunchDescription([
        # Wrap the remap and the include inside a GroupAction
        GroupAction(
            actions=[
                IncludeLaunchDescription(
                    XMLLaunchDescriptionSource(
                        os.path.join(get_package_share_directory('ranger_bringup'), 'launch', 'ranger_mini_v2.launch.xml')
                    ),
                    launch_arguments={
                        'base_frame': 'base_footprint',
                    }.items()
                )
            ]
        )
    ])