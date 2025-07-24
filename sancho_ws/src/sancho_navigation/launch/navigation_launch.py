import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetParameter


def generate_launch_description():
    # Configurable launch arguments
    use_sim_time = LaunchConfiguration("use_sim_time")
    autostart = LaunchConfiguration("autostart")
    use_respawn = LaunchConfiguration("use_respawn")
    prefix_cmd = LaunchConfiguration('prefix')

    nav2_params_path = os.path.join(
        get_package_share_directory("sancho_navigation"),
        "config",
        "nav2_params_ranger.yaml",
    )
    depthimage_to_laserscan_params = os.path.join(
        get_package_share_directory("sancho_navigation"),
        "config",
        "depthimage_to_laserscan_params.yaml",
    )

    lifecycle_nodes = [
        "map_server",
        "map_server_localization",
        "amcl",
        "planner_server",
        "controller_server",
        "behavior_server",
        "bt_navigator",
        "collision_monitor",
    ]

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="false", description="Use simulation time"
    )

    declare_autostart = DeclareLaunchArgument(
        "autostart", default_value="true", description="Startup all nav2 nodes"
    )

    declare_use_respawn = DeclareLaunchArgument(
        "use_respawn", default_value="true", description="Auto respawn nodes if they crash"
    )

    # Common remappings
    remappings = [
        ("cmd_vel_in", "cmd_vel_raw"),
        ("cmd_vel_out", "cmd_vel"),
    ]

    # Grupo de nodos
    nav2_nodes = GroupAction(
        actions=[
            SetParameter(name="use_sim_time", value=use_sim_time),

            Node(
                package="nav2_collision_monitor",
                executable="collision_monitor",
                name="collision_monitor",
                parameters=[nav2_params_path],
                remappings=remappings,
                respawn=use_respawn,
                output="screen",
            ),
            Node(
                package="nav2_map_server",
                executable="map_server",
                name="map_server",
                parameters=[nav2_params_path],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_map_server",
                executable="map_server",
                name="map_server_localization",
                parameters=[nav2_params_path],
                remappings=[("/map", "/localization_map")],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_amcl",
                executable="amcl",
                name="amcl",
                parameters=[nav2_params_path],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_planner",
                executable="planner_server",
                name="planner_server",
                parameters=[nav2_params_path],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_controller",
                executable="controller_server",
                name="controller_server",
                parameters=[nav2_params_path],
                remappings=[("cmd_vel", "cmd_vel")],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_bt_navigator",
                executable="bt_navigator",
                name="bt_navigator",
                parameters=[nav2_params_path],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_behaviors",
                executable="behavior_server",
                name="behavior_server",
                parameters=[nav2_params_path],
                output="screen",
                respawn=use_respawn,
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_navigation",
                parameters=[
                    {"use_sim_time": use_sim_time, "autostart": autostart, "node_names": lifecycle_nodes, "bond_timeout": 10.0}
                ],
                output="screen",
            ),
        ]
    )

    depth_scan_node = Node(
        package="depthimage_to_laserscan",
        executable="depthimage_to_laserscan_node",
        name="depthimage_to_laserscan",
        parameters=[depthimage_to_laserscan_params],
        remappings=[
            ("depth_camera_info", "/astra_camera/camera/depth/camera_info"),
            ("depth", "/astra_camera/camera/depth/image_raw"),
            ("scan", "/scan_camera"),
        ],
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'prefix',
            default_value='xterm -hold -e' if os.environ.get('DISPLAY') else '',
            description='Prefijo para lanzar nodos en terminal'
        ),
        declare_use_sim_time,
        declare_autostart,
        declare_use_respawn,
        nav2_nodes,
        depth_scan_node
    ])
