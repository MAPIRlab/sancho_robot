cmake_minimum_required(VERSION 3.8)
project(sancho_bt_plugins)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 1. Buscar paquetes necesarios
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav2_behavior_tree REQUIRED)
find_package(behaviortree_cpp_v3 REQUIRED)
find_package(geometry_msgs REQUIRED)

# 2. Crear la librería compartida
add_library(sancho_bt_plugins SHARED
  src/is_localized_condition.cpp
)

# 3. Incluir directorios de cabecera
target_include_directories(sancho_bt_plugins PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# Definición importante para registrar correctamente nodos custom
target_compile_definitions(sancho_bt_plugins PRIVATE BT_PLUGIN_EXPORT)

# 4. Vincular librerías (Linker)
ament_target_dependencies(sancho_bt_plugins
  rclcpp
  nav2_behavior_tree
  behaviortree_cpp_v3
  geometry_msgs
)

# 5. Reglas de instalación (para que 'colcon build' ponga los archivos donde deben ir)
install(TARGETS sancho_bt_plugins
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include
)

# 6. Exportar dependencias para otros paquetes
ament_export_include_directories(include)
ament_export_libraries(sancho_bt_plugins)
ament_export_dependencies(rclcpp nav2_behavior_tree behaviortree_cpp_v3 geometry_msgs)

ament_package()