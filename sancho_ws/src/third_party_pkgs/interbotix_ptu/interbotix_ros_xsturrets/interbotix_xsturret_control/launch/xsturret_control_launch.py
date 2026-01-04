import os

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, OpaqueFunction, GroupAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.parameter_descriptions import ParameterFile
from launch_ros.actions import Node, PushRosNamespace
from ament_index_python.packages import get_package_share_directory
import xacro

def launch_setup(context, *args, **kwargs):
    # Get the launch directory
    xsturret_control_dir = get_package_share_directory("interbotix_xsturret_control")
    xsturret_desc_dir = get_package_share_directory("interbotix_xsturret_descriptions")
    namespace = LaunchConfiguration('namespace').perform(context)
    "$(find interbotix_xsturret_control)/config/modes.yaml"
    
           
    interbotix_nodes =[
        # SDK
        Node(
            package='interbotix_xs_sdk',
            executable='xs_sdk',
            name='xs_sdk',
            output='screen',
            prefix='xterm -hold -e',
            parameters=[{
                "motor_configs": os.path.join(xsturret_control_dir, 'config', 'wxxms.yaml'),
                "mode_configs": os.path.join(xsturret_control_dir, 'config', 'modes.yaml'),
                "load_configs": False,
            }]
            ),
    ]
    
    # URDF model (TFs)
    robot_desc = xacro.process_file(os.path.join(xsturret_desc_dir, 'urdf', 'wxxms.urdf.xacro'), mappings={'frame_ns': namespace})
    robot_desc = robot_desc.toprettyxml(indent='  ')
    robot_state_publisher = [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc}]           
            ),
    ]
            
    # RVIZ
    rviz=[
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            prefix="xterm -hold -e",
            #arguments=['-d' + rviz_file],
        ),
    ]
    

    actions=[PushRosNamespace(namespace)]
    actions.extend(interbotix_nodes)
    actions.extend(robot_state_publisher)
    actions.extend(rviz)
    return[
        GroupAction
        (
            actions=actions
        )
    ]


def generate_launch_description():

    return LaunchDescription([
        # Set env var to print messages to stdout immediately
        SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'),
        
        DeclareLaunchArgument(
            "log_level",
            default_value=["info"],  #debug, info
            description="Logging level",
            ),
        DeclareLaunchArgument('namespace', default_value="rhodon"),
        OpaqueFunction(function = launch_setup)
    ])
