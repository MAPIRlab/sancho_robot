import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    hw_pkg = get_package_share_directory('sancho_hardware')

    return LaunchDescription([
        # 1. Base Ranger
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(hw_pkg, 'launch', 'ranger_wrapper.launch.py'))
        ),
        # 2. LiDARs (Wrapper)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(hw_pkg, 'launch', 'lidars_wrapper.launch.py'))
        ),
        # 3. Astra (Wrapper)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(hw_pkg, 'launch', 'astra_wrapper.launch.py'))
        ),
        # 4. Nose Cam (The file you moved to hardware)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(hw_pkg, 'launch', 'nose_cam.launch.py'))
        ),
        # 5. Head
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(hw_pkg, 'launch', 'head.launch.py'))
        ),
    ])