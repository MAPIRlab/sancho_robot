cmake_minimum_required(VERSION 3.8)
project(sancho_hardware)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sancho_interfaces REQUIRED)

# PortAudio and FFTW for C++ node
find_package(PkgConfig REQUIRED)
pkg_check_modules(PORTAUDIO REQUIRED portaudio-2.0)

# ----------------------------------------------------------------------------
# C++ Nodes
# ----------------------------------------------------------------------------
add_executable(face_node src/face_node.cpp)
ament_target_dependencies(face_node rclcpp std_msgs)

target_include_directories(face_node PRIVATE
  ${PORTAUDIO_INCLUDE_DIRS}
)

target_link_libraries(face_node
  ${PORTAUDIO_LIBRARIES}
  fftw3
)

install(TARGETS
  face_node
  DESTINATION lib/${PROJECT_NAME}
)

# ----------------------------------------------------------------------------
# Python Module and Nodes
# ----------------------------------------------------------------------------
# Install the Python package/module
ament_python_install_package(${PROJECT_NAME})

# Install the Python scripts as executables so `ros2 run` can find them
install(PROGRAMS
  ${PROJECT_NAME}/head_control/head_controller_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME head_controller_node
)

# Install test_face_emotions.py
install(PROGRAMS
  ${PROJECT_NAME}/test_face_emotions.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME test_face_emotions
)

# Install resource folders or other data
install(DIRECTORY resource/
  DESTINATION share/${PROJECT_NAME}/resource
)

# Install launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

ament_package()
