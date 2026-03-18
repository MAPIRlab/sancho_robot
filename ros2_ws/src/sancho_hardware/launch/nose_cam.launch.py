import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    hw_pkg = get_package_share_directory('sancho_hardware')
    usb_cam_param_file = os.path.join(hw_pkg, 'config', 'cameras', 'params_640.yaml')

    return LaunchDescription([
        Node(
            package='usb_cam',
            executable='usb_cam_node_exe',
            name='usb_cam_node',
            output='screen',
            parameters=[usb_cam_param_file],
            remappings=[
                ('/image_raw', '/sancho_camera/image_raw'),
                ('/camera_info', '/sancho_camera/camera_info')
            ]
        ),
        Node(
            package='image_proc',
            executable='rectify_node',
            name='usb_cam_rectify_node',
            output='screen',
            remappings=[
                ('image', '/sancho_camera/image_raw'),
                ('camera_info', '/sancho_camera/camera_info'),
                ('image_rect', '/sancho_camera/image_rect')
            ],
            parameters=[{'queue_size': 5}]
        )
    ])