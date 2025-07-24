from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Nodo rosbridge_websocket
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen',
            parameters=[
                {'port': 9090},
                {'address': '0.0.0.0'},
                {'reject_bytes': False},
                {'default_call_service_timeout': 5.0},
                {'call_services_in_new_thread': True},
                {'send_action_goals_in_new_thread': True},
            ],
        ),

        # Nodo rosapi (necesario para /rosapi/topics, /rosapi/services, etc.)
        Node(
            package='rosapi',
            executable='rosapi_node',
            name='rosapi_node',
            output='screen',
        ),

       
    ])
