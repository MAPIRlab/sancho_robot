cmake_minimum_required(VERSION 3.8)
project(sancho_bt_plugins)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# =========================
# Dependencies
# =========================
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav2_behavior_tree REQUIRED)
find_package(behaviortree_cpp_v3 REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(pluginlib REQUIRED)

# =========================
# Library
# =========================
add_library(sancho_bt_plugins SHARED
  src/is_localized_condition.cpp
)

target_include_directories(sancho_bt_plugins PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# Required for BT plugin symbol export
target_compile_definitions(sancho_bt_plugins PRIVATE BT_PLUGIN_EXPORT)

ament_target_dependencies(sancho_bt_plugins
  rclcpp
  nav2_behavior_tree
  behaviortree_cpp_v3
  geometry_msgs
  pluginlib
)

# =========================
# Installation
# =========================
install(TARGETS sancho_bt_plugins
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include
)

# IMPORTANT: install plugin.xml
install(FILES plugin.xml
  DESTINATION share/${PROJECT_NAME}
)

# =========================
# Plugin export
# =========================
pluginlib_export_plugin_description_file(behaviortree_cpp_v3 plugin.xml)

# =========================
# Export for downstream packages
# =========================
ament_export_include_directories(include)
ament_export_libraries(sancho_bt_plugins)
ament_export_dependencies(
  rclcpp
  nav2_behavior_tree
  behaviortree_cpp_v3
  geometry_msgs
  pluginlib
)

ament_package()