import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'sancho_perception'

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
    description='A package providing perception functionalities for move detection and group processing.',
    license='GPL-3.0-or-later',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'movenet_inference_node = sancho_perception.movenet_inference_node:main',
            'movenet_postprocessing_node = sancho_perception.movenet_postprocessing_node:main',
            'group_detection_node = sancho_perception.group_detection_node:main',
            'group_waypoint_generator_node = sancho_perception.group_waypoint_generator_node:main',
            'relay_metrics_node = sancho_perception.metrics_node:main',
            'perception_test = sancho_perception.perception_test:main',
        ],
    },
)
