cmake_minimum_required(VERSION 3.8)
project(face_controller)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Dependencias ROS
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

# PortAudio y FFTW
find_package(PkgConfig REQUIRED)
pkg_check_modules(PORTAUDIO REQUIRED portaudio-2.0)

# Ejecutable
add_executable(face_node src/face_node.cpp)
ament_target_dependencies(face_node rclcpp std_msgs)

target_include_directories(face_node PRIVATE
  ${PORTAUDIO_INCLUDE_DIRS}
)

target_link_libraries(face_node
  ${PORTAUDIO_LIBRARIES}
  fftw3
)

# Instalación
install(TARGETS
  face_node
  DESTINATION lib/${PROJECT_NAME})

ament_package()
