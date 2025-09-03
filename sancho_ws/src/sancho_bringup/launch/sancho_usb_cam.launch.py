import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    # Ruta a tu archivo de parámetros custom de la cámara
    usb_cam_param_file = os.path.join(
        get_package_share_directory('sancho_bringup'),
        'config',
        'params_mid.yaml'   
    )

    # Nodo de cámara USB
    usb_cam_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam_node',
        output='screen',
        parameters=[usb_cam_param_file],
        remappings=[
            ('/image_raw', '/sancho_camera/image_raw'),  # Remapear a namespace ordenado
            ('/camera_info', '/sancho_camera/camera_info')
        ]
    )

    image_proc_node = Node(
            package='image_proc',
            executable='rectify_node',
            name='usb_cam_rectify_node',
            output='screen',
            remappings=[
                ('image', '/sancho_camera/image_raw'),
                ('camera_info', '/sancho_camera/camera_info'),
                ('image_rect', '/sancho_camera/image_rect')
            ]
        )
    return LaunchDescription([
        usb_cam_node,
        image_proc_node
    ])
