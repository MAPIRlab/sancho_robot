from setuptools import find_packages, setup

package_name = 'sancho_hri'

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
    maintainer='pablo',
    maintainer_email='todo@todo.com',
    description='Unified HRI and AI tooling for Sancho',
    license='TODO',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'llm = sancho_hri.llm.llm_node:main','test_all = sancho_hri.llm.test_all_node:main','stt = sancho_hri.speech.stt_node:main','tts = sancho_hri.speech.tts_node:main','sancho_ai = sancho_hri.ai.sancho_ai_node:main','embedding_generator = sancho_hri.ai.embedding_generator_node:main','test_llm_classification = sancho_hri.ai.test_llm_classification_node:main','test_embedding_classification = sancho_hri.ai.test_embedding_classification_node:main'
        ],
    },
)
