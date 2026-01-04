from setuptools import find_packages, setup

package_name = 'ros2web'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml'])
    ],
        install_requires=['setuptools', 'flask', 'pytest', 'rclpy', 'websockets', 'werkzeug'],
    zip_safe=True,
    maintainer='eulogioqt',
    maintainer_email='euquemada@gmail.com',
    description='Websocket bridge between ROS 2 and web clients',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'server = ros2web.server_node:main'
        ],
    },
)
