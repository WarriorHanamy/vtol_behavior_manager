cmake_minimum_required(VERSION 3.8)
project(neural_gate)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)

add_executable(neural_gate_node src/neural_gate.cpp)
ament_target_dependencies(neural_gate_node rclcpp px4_msgs)

install(TARGETS neural_gate_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
