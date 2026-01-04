import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch_ros.actions import Node, PushRosNamespace
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch.actions import ExecuteProcess

def generate_launch_description():
    ranger_bringup_path = get_package_share_directory('ranger_bringup')

    # Ruta a tu archivo de parámetros custom de la cámara
    usb_cam_param_file = os.path.join(
        get_package_share_directory('sancho_bringup'),
        'config',
        'params_mid.yaml'   
    )

    # Lanzar LiDAR Hokuyo
    hokuyo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('urg_node2'), 'launch', 'urg_node2_2lidar.launch.py')
        )
    )



    # Lanzar cámara Astra
    astra_camera_launch = GroupAction([
        PushRosNamespace('astra_camera'),
        IncludeLaunchDescription(
            XMLLaunchDescriptionSource(
                os.path.join(get_package_share_directory('astra_camera'), 'launch', 'astra.launch.xml')
            ),
            launch_arguments={
                'serial_number': "'20070830098'",
                'camera_name': 'camera',
                'color_fps': '15',
                'depth_fps': '15',
                'ir_fps': '15'
            }.items()
        )
    ])

    # Base móvil Ranger
    ranger_launch = IncludeLaunchDescription(
        XMLLaunchDescriptionSource(os.path.join(ranger_bringup_path, 'launch', 'ranger_mini_v2.launch.xml')),
        launch_arguments={
            'base_frame': 'base_footprint',
        }.items()
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
    
    scan_merger_node =  Node(
            package='laser_scan_merger',
            executable='laser_scan_merger',
            name='laser_scan_merger',
            output='screen',
            parameters=[{
                'scanTopic1': '/scan_1st',
                'scanTopic2': '/scan_2nd',
                'target_frame': 'base_link',
                'laser1_frame': 'laser_front',
                'laser2_frame': 'laser_back',
                'point_cloud_topic': 'scan_merged',
                'pointCloutFrameId': 'base_link',
                'pointCloudTopic':  '/laser_cloud',
            }]
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
        # Comandos para configurar la cámara
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'white_balance_automatic=0'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'white_balance_temperature=4600'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'auto_exposure=1'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'exposure_time_absolute=157'], shell=False),
        ExecuteProcess(cmd=['v4l2-ctl', '-d', '/dev/video0', '-c', 'exposure_dynamic_framerate=0'], shell=False),


        # Nodo de conversión de nube de puntos a láser
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='cloud_to_scan',
            output='screen',
            remappings=[
                ('cloud_in', '/laser_cloud'),
                ('scan', '/scan_merged')
            ],
            parameters=[{
                'target_frame': 'base_link',
                'transform_tolerance': 0.01,
                'min_height': -1.0,
                'max_height': 1.0,
                'angle_min': -3.14,
                'angle_max': 3.14,
                'angle_increment': 0.008,
                'scan_time': 0.1,
                'range_min': 0.1,
                'range_max': 30.0,
                'use_inf': True,
                'inf_epsilon': 1.0
            }]
        ),

        # Base móvil y sensores
        ranger_launch,
        hokuyo_launch,
        astra_camera_launch,
        scan_merger_node,
        usb_cam_node,
        image_proc_node
    ])
