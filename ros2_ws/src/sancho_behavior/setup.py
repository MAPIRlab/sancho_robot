from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'sancho_behavior'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pablo',
    maintainer_email='todo@todo.com',
    description='Unified Behavior layer for Sancho',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'orchestrator_node = sancho_behavior.orchestrator.orchestrator_node:main',
<<<<<<< HEAD:sancho_ws/src/sancho_behavior/setup.py
            'attention_manager_node = sancho_behavior.interaction.attention_manager_node:main',
            'interaction_manager_node = sancho_behavior.interaction.interaction_manager_node:main'
=======
            'interaction_manager_node = sancho_behavior.interaction.interaction_manager_node:main',
            'attention_manager_node = sancho_behavior.interaction.attention_manager_node:main'
>>>>>>> refactor:ros2_ws/src/sancho_behavior/setup.py
        ],
    },
)
