import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'sancho_head_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join("share", package_name, "launch"), glob("launch/*")),

    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='antbaena',
    maintainer_email='antbaena@uma.es',
    description='The sancho_head_control package offers ROS2 nodes for head control and tracking, enabling precise manipulation and orientational adjustments in robotic systems.',
    license='GPL-3.0-or-later',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'head_controller_node = sancho_head_control.head_controller_node:main',
            'head_tracker_node = sancho_head_control.head_tracker_node:main',
            
        ],
    },
)
