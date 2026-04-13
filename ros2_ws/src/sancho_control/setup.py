from setuptools import find_packages, setup

package_name = 'sancho_control'

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
    maintainer='mapir',
    maintainer_email='pablohorjim@uma.es',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'head_control_face_tracker = sancho_control.head_control_face_tracker_node:main',
            'head_action_server = sancho_control.head_action_server:main',
            'turn_action_server = sancho_control.turn_action_server:main'
        ],
    },
)
