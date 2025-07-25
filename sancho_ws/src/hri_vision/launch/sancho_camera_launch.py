import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch_ros.actions import Node, PushRosNamespace
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch.actions import ExecuteProcess

def generate_launch_description():
    usb_cam_param_file = os.path.join(
        get_package_share_directory('hri_vision'),
        'config',
        'params_mid.yaml'
    )
    usb_cam_node = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam_node',
        output='screen',
        parameters=[usb_cam_param_file],
        remappings=[
            ('/image_raw', '/sancho_camera/image_raw'),
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
                ('image_rect', '/camera/color/image_raw')
            ]
        )
    
    return LaunchDescription([
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'white_balance_automatic=0'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'white_balance_temperature=4600'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'auto_exposure=1'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'exposure_time_absolute=157'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'exposure_dynamic_framerate=0'], shell=False),
        usb_cam_node,
        image_proc_node
    ])