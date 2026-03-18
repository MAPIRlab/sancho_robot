cmake_minimum_required(VERSION 3.8)
project(interbotix_xsturret_control)

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(interbotix_xs_sdk)
find_package(interbotix_xs_modules)
find_package(interbotix_xsturret_descriptions)


###################################
## catkin specific configuration ##
###################################
## The catkin_package macro generates cmake config files for your package
## Declare things to be passed to dependent projects
#catkin_package(
#  CATKIN_DEPENDS interbotix_xs_sdk interbotix_xs_modules interbotix_xsturret_descriptions
#)

# Install launch files and related config files.
install(DIRECTORY
  launch
  config
  images
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()
