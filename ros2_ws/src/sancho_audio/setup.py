import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'sancho_audio'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    package_data={package_name: ['utils/models/*.onnx', 'sounds/*.wav']},
    include_package_data=True,
    

    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'models'), glob('sancho_audio/utils/models/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'sounds'), glob(package_name + '/sounds/*.wav')),
        (os.path.join('share', package_name, 'utils', 'models'), glob(package_name + '/utils/models/*.onnx'))
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
            'audio_gateway=sancho_audio.audio_gateway_node:main',
            'audio_doa_xvf3800_lifecycle=sancho_audio.audio_doa_xvf3800_lifecycle_node:main',
            'vad_transcriptor_node=sancho_audio.vad_transcriptor_node:main',
            'doa_active_speaker=sancho_audio.doa_active_speaker_node:main',
            'microphone=sancho_audio.legacy.microphone_node:main'
        ],
    },
)
