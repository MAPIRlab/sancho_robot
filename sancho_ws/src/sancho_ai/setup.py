from glob import glob
from setuptools import find_packages, setup

package_name = 'sancho_ai'

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
        package_name: ['prompts/commands/*.json'],
    },
    include_package_data=True,
        install_requires=['setuptools', 'dotenv', 'numpy', 'pytest', 'rclpy'],
    zip_safe=True,
    maintainer='eulogioqt',
    maintainer_email='euquemada@gmail.com',
    description='AI nodes for LLM-based conversation and embeddings',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'sancho_ai = sancho_ai.sancho_ai_node:main',
            'embedding_generator = sancho_ai.embedding_generator_node:main',
            'test_llm_classification = sancho_ai.test_llm_classification_node:main',
            'test_embedding_classification = sancho_ai.test_embedding_classification_node:main',
            'test_asking = sancho_ai.test_asking_node:main',
        ],
    },
)
