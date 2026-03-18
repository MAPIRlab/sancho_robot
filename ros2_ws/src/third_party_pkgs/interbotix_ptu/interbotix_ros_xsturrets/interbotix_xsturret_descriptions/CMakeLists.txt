cmake_minimum_required(VERSION 3.8)
project(interbotix_xsturret_descriptions)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(joint_state_publisher)
find_package(joint_state_publisher_gui)
find_package(robot_state_publisher)
find_package(roslaunch)
find_package(rviz2)
find_package(xacro)

###################################
## catkin specific configuration ##
###################################
## The catkin_package macro generates cmake config files for your package
## Declare things to be passed to dependent projects
#catkin_package(
#  CATKIN_DEPENDS joint_state_publisher joint_state_publisher_gui robot_state_publisher roslaunch rviz xacro
#)

###########
## Build ##
###########

## Specify additional locations of header files
## Your package locations should be listed before other locations
#include_directories(
#  ${catkin_INCLUDE_DIRS}
#)


# Install launch files and related config files.
install(DIRECTORY
  launch
  meshes
  images
  rviz
  urdf
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()