from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
import os
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    urdf_file =  os.path.join(
        get_package_share_directory('sancho_description'),
        'urdf',
        'sancho_ranger.urdf'
    )
    
    return LaunchDescription([
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{"robot_description": open(urdf_file).read()}],
            remappings=[("/joint_states", "/joint_states_merged")]

        ),
        Node(
            package="joint_state_publisher",
            executable="joint_state_publisher",
            name="joint_state_publisher",
            output="screen",
            parameters=[{"use_sim_time": False}],
            remappings=[("/joint_states", "/joint_states_urdf")],
        ),
        Node(
            package="sancho_description",
            executable="joint_state_merger_node",
            name="joint_state_merger_node",
            output="screen",
        ),

        # Node(
        #     package="rviz2",
        #     executable="rviz2",
        #     name="rviz2",
        #     output="screen",
        # )
    ])
