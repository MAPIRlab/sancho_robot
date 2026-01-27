import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    # Configurable launch arguments
    use_sim_time = LaunchConfiguration("use_sim_time")
    autostart = LaunchConfiguration("autostart")
    use_respawn = LaunchConfiguration("use_respawn")
    prefix_cmd = LaunchConfiguration('prefix')
    map_yaml_file = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    default_bt_xml_filename = LaunchConfiguration('default_bt_xml_filename')

    pkg_share = get_package_share_directory("sancho_navigation")
    
    # Define paths to new discrete config files
    localization_params_path = os.path.join(pkg_share, "config", "localization_params.yaml")
    controller_params_path = os.path.join(pkg_share, "config", "controller_params.yaml")
    planner_params_path = os.path.join(pkg_share, "config", "planner_params.yaml")
    behavior_params_path = os.path.join(pkg_share, "config", "behavior_params.yaml")
    collision_monitor_params_path = os.path.join(pkg_share, "config", "collision_monitor_params.yaml")

    depthimage_to_laserscan_params = os.path.join(pkg_share,"config","depthimage_to_laserscan_params.yaml")

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

    # RewrittenYaml for parameterized config injection (Map & BT XML)
    # We create specific RewrittenYaml instances for nodes that need dynamic paths
    
    # 1. Localization (Map Server) relies on 'map' arg relative path handling logic
    # Actually, map_server just takes 'yaml_filename' param.
    configured_localization_params = RewrittenYaml(
        source_file=localization_params_path,
        root_key="",
        param_rewrites={"yaml_filename": map_yaml_file},
        convert_types=True
    )

    # 2. BT Navigator relies on 'default_nav_to_pose_bt_xml'
    configured_behavior_params = RewrittenYaml(
        source_file=behavior_params_path,
        root_key="",
        param_rewrites={"default_nav_to_pose_bt_xml": default_bt_xml_filename},
        convert_types=True
    )


    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="false", description="Use simulation time"
    )

    declare_autostart = DeclareLaunchArgument(
        "autostart", default_value="true", description="Startup all nav2 nodes"
    )

    declare_use_respawn = DeclareLaunchArgument(
        "use_respawn", default_value="true", description="Auto respawn nodes if they crash"
    )
    
    declare_map_yaml_cmd = DeclareLaunchArgument(
        'map',
        default_value=os.path.join(pkg_share, 'maps', 'mapir_lab_navigation.yaml'),
        description='Full path to map configuration file to load'
    )

    declare_bt_xml_cmd = DeclareLaunchArgument(
        'default_bt_xml_filename',
        default_value=os.path.join(pkg_share, 'bt', 'testBT.xml'),
        description='Full path to the behavior tree xml file to use'
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
            
            # --- Collision Monitor ---
            Node(
                package="nav2_collision_monitor",
                executable="collision_monitor",
                name="collision_monitor",
                parameters=[collision_monitor_params_path],
                remappings=remappings,
                respawn=use_respawn,
                output="screen",
            ),
            
            # --- Map Servers ---
            Node(
                package="nav2_map_server",
                executable="map_server",
                name="map_server",
                parameters=[configured_localization_params],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            Node(
                package="nav2_map_server",
                executable="map_server",
                name="map_server_localization",
                parameters=[configured_localization_params],
                remappings=[("/map", "/localization_map")],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            
            # --- AMCL ---
            Node(
                package="nav2_amcl",
                executable="amcl",
                name="amcl",
                parameters=[localization_params_path], # AMCL params are static
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            
            # --- Planner ---
            Node(
                package="nav2_planner",
                executable="planner_server",
                name="planner_server",
                parameters=[planner_params_path],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            
            # --- Controller ---
            Node(
                package="nav2_controller",
                executable="controller_server",
                name="controller_server",
                parameters=[controller_params_path],
                remappings=[("cmd_vel", "cmd_vel")],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            
            # --- BT Navigator ---
            Node(
                package="nav2_bt_navigator",
                executable="bt_navigator",
                name="bt_navigator",
                parameters=[configured_behavior_params],
                output="screen",
                prefix=prefix_cmd,
                emulate_tty=True,
                respawn=use_respawn,
            ),
            
            # --- Behavior Server ---
            Node(
                package="nav2_behaviors",
                executable="behavior_server",
                name="behavior_server",
                parameters=[behavior_params_path],
                output="screen",
                respawn=use_respawn,
            ),
            
            # --- Lifecycle Manager ---
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
        declare_map_yaml_cmd,
        declare_bt_xml_cmd,
        nav2_nodes,
        depth_scan_node
    ])
