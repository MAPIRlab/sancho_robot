from setuptools import find_packages, setup

package_name = 'sancho_web_bridge'

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
    maintainer='pablohorjim',
    maintainer_email='pablohorjim@uma.es',
    description='Unified Web Bridge for Sancho',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'server = sancho_web_bridge.rosbridge.server_node:main','sancho_web_assistant = sancho_web_bridge.assistant.sancho_web_bridge.assistant_node:main','api_rest = sancho_web_bridge.assistant.api_rest_node:main','database_manager = sancho_web_bridge.assistant.database_manager_node:main','session_manager = sancho_web_bridge.rumi.session_manager_node:main'
        ],
    },
)
