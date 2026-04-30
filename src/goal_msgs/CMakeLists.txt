cmake_minimum_required(VERSION 3.8)
project(goal_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/GoalHover.msg"
  "msg/GoalAcro.msg"
  "msg/NeuralTarget.msg"
)

ament_package()
