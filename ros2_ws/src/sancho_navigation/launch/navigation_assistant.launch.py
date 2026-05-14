from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import TimerAction

def generate_launch_description():
    # Definición de los nodos con sus parámetros específicos
    
    topology_node = Node(
        package='topology_graph',
        executable='topology_graph_node',
        output='screen'
    )

    # El asistente de navegación espera a que la topología arranque (2 segundos)
    nav_assistant_node = TimerAction(
        period=2.0,
        actions=[
            Node(
                package='navigation_assistant',
                executable='nav_assistant_node',
                parameters=[{
                    'init_from_json_file': '/home/mapir/sancho_robot/ros2_ws/src/sancho_navigation/maps/topo_module2.3.json',
                    'load_passages_as_CP': True
                }],
                output='screen'
            )
        ]
    )

    # Las funciones de asistencia esperan un poco más (4 segundos en total)
    nav_functions_node = TimerAction(
        period=4.0,
        actions=[
            Node(
                package='nav_assistant_functions',
                executable='nav_assistant_functions_node',
                arguments=['--radius=0.35'],
                output='screen'
            )
        ]
    )

    return LaunchDescription([
        topology_node,
        nav_assistant_node,
        nav_functions_node
    ])