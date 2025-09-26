import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'sancho_vision'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py'))
    ],
    package_data={
        package_name: ['models/*', 'fonts/*', 'database/*.json', 'gui/*.qss', 'gui/*.png'],
    },
    include_package_data=True,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='antbaena, eulogioqt',
    maintainer_email='antbaena@uma.es, eulogioquemada@uma.es',
    description='A vision module providing face detection and tracking functionality with lifecycle management.',
    license='GPL-3.0-or-later',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'face_detector_lifecycle_node = sancho_vision.face_detector_lifecycle_node:main',
            'face_tracker_lifecycle_node = sancho_vision.face_tracker_lifecycle_node:main',
            'face_cluster_node = sancho_vision.face_cluster_node:main',
            'central_faces_cluster_node = sancho_vision.central_faces_cluster_node:main',

            'human_face_detector_lifecycle = sancho_vision.human_face_detector_lifecycle_node:main',       
            'human_face_recognizer_lifecycle = sancho_vision.human_face_recognizer_lifecycle_node:main',
            'human_face_manager_lifecycle = sancho_vision.human_face_manager_lifecycle_node:main',
            'gui = sancho_vision.hri_gui:main',

            'camera = sancho_vision.camera_node:main',
            'video = sancho_vision.video_node:main',
        ],
    },
)
