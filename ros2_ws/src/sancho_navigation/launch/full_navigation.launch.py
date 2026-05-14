import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Obtener la ruta de instalación del paquete sancho_navigation
    nav_pkg_share = FindPackageShare('sancho_navigation')

    # 1. Lanzar la navegación base (Nav2) bloqueando las ventanas de terminal
    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([nav_pkg_share, '/launch/navigation.launch.py']),
        # ¡Esta es la clave! Sobrescribimos el argumento 'prefix' con una cadena vacía
        # Esto anula el 'xterm -hold -e' de tu archivo original para este lanzamiento.
        launch_arguments={
            'prefix': ''
        }.items()
    )

    # 2. Lanzar el asistente de navegación
    nav_assistant_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([nav_pkg_share, '/launch/navigation_assistant.launch.py'])
    )

    return LaunchDescription([
        navigation_launch,
        nav_assistant_launch
    ])