from glob import glob
from setuptools import find_packages, setup

package_name = 'sancho_web_assistant'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + "/commands", glob(package_name + '/commands/*.json'))
    ],
    package_data={
        package_name: ['database/*.db'],
    },
    include_package_data=True,
        install_requires=['setuptools', 'dotenv', 'fastapi', 'pydantic', 'pytest', 'rclpy', 'uvicorn', 'websockets'],
    zip_safe=True,
    maintainer='eulogioqt',
    maintainer_email='euquemada@gmail.com',
    description='Web APIs exposing Sancho AI services',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'sancho_web_assistant = sancho_web_assistant.sancho_web_assistant_node:main',
            'api_rest = sancho_web_assistant.api_rest_node:main',
            'database_manager = sancho_web_assistant.database_manager_node:main'
        ],
    },
)
