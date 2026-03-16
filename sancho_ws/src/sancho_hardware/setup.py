from setuptools import find_packages, setup

package_name = 'sancho_hardware'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pablo',
    maintainer_email='todo@todo.com',
    description='Unified Hardware Integrations for Sancho',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'head_controller_node = sancho_hardware.head_control.head_controller_node:main','head_tracker_node = sancho_hardware.head_control.head_tracker_node:main'
        ],
    },
)
