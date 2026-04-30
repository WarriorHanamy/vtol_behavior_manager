cmake_minimum_required(VERSION 3.8)
project(neural_gate)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(goal_msgs REQUIRED)

add_executable(neural_gate_hover src/neural_gate_hover.cpp)
ament_target_dependencies(neural_gate_hover rclcpp px4_msgs goal_msgs)

add_executable(neural_gate_acro src/neural_gate_acro.cpp)
ament_target_dependencies(neural_gate_acro rclcpp px4_msgs goal_msgs)

install(TARGETS neural_gate_hover neural_gate_acro
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
