import os
from setuptools import find_packages, setup

package_name = 'sancho_bringup'

# 1. Base required data files
data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
]

# 2. Dynamically crawl folders
# This will find your 3 new launch files (bringup, hardware, processing)
# and any global configs left in 'config'
for directory in ['launch']:
    for path, _, filenames in os.walk(directory):
        if filenames:
            install_dir = os.path.join('share', package_name, path)
            file_paths = [os.path.join(path, f) for f in filenames]
            data_files.append((install_dir, file_paths))

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pablohorjim',
    maintainer_email='pablohorjim@uma.es',
    description='Orchestration package for Sancho robot - Layered launch system.',
    license='GPL-3.0-or-later',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        ],
    },
)