import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'sancho_navigation'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join("share", package_name, "launch"), glob("launch/*")),
        (os.path.join("share", package_name, "config"), glob("config/*")),
        (os.path.join("share", package_name, "maps"), glob("maps/*")),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='antbaena',
    maintainer_email='antbaena@uma.es',
    description='A navigation package providing nodes and resources for robotic movement and configuration.',
    license='GPL-3.0-or-later',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'roaming_node = sancho_navigation.roaming_node:main',
        ],
    },
)
