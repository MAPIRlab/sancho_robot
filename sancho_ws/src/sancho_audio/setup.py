import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'sancho_audio'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='antbaena',
    maintainer_email='antbaena@uma.es',
    description='A package for ROS 2 audio interaction, providing tools for audio playback, directional sound processing, microphone capture, voice activity detection, and stereo recording.',
    license='GPL-3.0-or-later',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'audio_player = sancho_audio.audio_player_node:main',
            'audio_direction = sancho_audio.audio_direction_node:main',
            'microphone_capturer = sancho_audio.microphone_capturer_node:main',
            'voice_activity_detector = sancho_audio.vad_node:main',
            'stereo_recorder = sancho_audio.stereo_recorder_node:main',
        ],
    },
)
