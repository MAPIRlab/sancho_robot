import os

from glob import glob
from setuptools import find_packages, setup

package_name = 'rumi_web'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name), glob('launch/*launch.[pxy][yma]*')),
    ],
    package_data={
        package_name: ['database/*.db'],
    },
    include_package_data=True,
        install_requires=['setuptools', 'pytest', 'rclpy'],
    zip_safe=True,
    maintainer='eulogioqt',
    maintainer_email='euquemada@gmail.com',
    description='Web interface to manage Rumi sessions',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'session_manager = rumi_web.session_manager_node:main',
        ],
    },
)
