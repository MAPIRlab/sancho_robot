from setuptools import find_packages, setup

package_name = 'llm_tools'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
        install_requires=['setuptools', 'dotenv', 'openai', 'pytest', 'rclpy', 'torch', 'transformers'],
    zip_safe=True,
    maintainer='eulogioqt',
    maintainer_email='euquemada@gmail.com',
    description='Tools and nodes to interact with LLM providers',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest']
    },
    entry_points={
        'console_scripts': [
            'llm = llm_tools.llm_node:main',
            'test_all = llm_tools.test_all_node:main'
        ],
    },
)
