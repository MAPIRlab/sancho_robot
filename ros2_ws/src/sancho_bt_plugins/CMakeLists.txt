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
find_package(nav_msgs REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(topology_graph REQUIRED)
find_package(tf2_ros REQUIRED)

# =========================
# Library 1: Is Localized
# =========================
add_library(is_localized_condition SHARED src/is_localized_condition.cpp)
target_include_directories(is_localized_condition PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_compile_definitions(is_localized_condition PRIVATE BT_PLUGIN_EXPORT)
ament_target_dependencies(is_localized_condition
  rclcpp
  nav2_behavior_tree
  behaviortree_cpp_v3
  geometry_msgs
  pluginlib
)

# =========================
# Library 2: Inject Waypoints
# =========================
add_library(inject_waypoints_node SHARED src/inject_waypoints_node.cpp)
target_include_directories(inject_waypoints_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_compile_definitions(inject_waypoints_node PRIVATE BT_PLUGIN_EXPORT)
ament_target_dependencies(inject_waypoints_node
  rclcpp
  nav2_behavior_tree
  behaviortree_cpp_v3
  geometry_msgs
  pluginlib
  nav_msgs
  tf2_geometry_msgs
  topology_graph
)


# =========================
# Installation
# =========================
install(TARGETS is_localized_condition inject_waypoints_node
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY include/
  DESTINATION include
)

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
ament_export_libraries(is_localized_condition inject_waypoints_node)
ament_export_dependencies(
  rclcpp
  nav2_behavior_tree
  behaviortree_cpp_v3
  geometry_msgs
  pluginlib
  nav_msgs
  tf2_geometry_msgs
  topology_graph
)

ament_package()