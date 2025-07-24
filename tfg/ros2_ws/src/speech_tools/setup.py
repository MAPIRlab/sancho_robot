from setuptools import find_packages, setup

package_name = 'speech_tools'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    package_data={
        package_name: ['tts/tts_models/*'],
    },
    include_package_data=True,
        install_requires=['setuptools', 'bark', 'gtts', 'numpy', 'pydub', 'pytest', 'rclpy', 'requests', 'scipy', 'sounddevice', 'soundfile', 'torch', 'torchaudio', 'tts'],
    zip_safe=True,
    maintainer='eulogioqt',
    maintainer_email='euquemada@gmail.com',
    description='Speech synthesis and recognition tools',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'stt=speech_tools.stt_node:main',
            'tts=speech_tools.tts_node:main'
        ],
    },
)
