cmake_minimum_required(VERSION 3.8)
project(isaac_pos_ctrl_neural)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies using ament_cmake_auto for C++ dependencies
find_package(ament_cmake_auto REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Auto-discover dependencies for C++
ament_auto_find_build_dependencies()

# Install Python package
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  ${PROJECT_NAME}/isaac_pos_ctrl_node.py
  ${PROJECT_NAME}/set_target_pos.py
  ${PROJECT_NAME}/math_utils.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files (already in setup.py data_files, but CMake install is also fine)
install(
  DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# Install config files (already in setup.py data_files, but CMake install is also fine)
install(
  DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
)

# Install model files (already in setup.py data_files, but CMake install is also fine)
install(
  DIRECTORY models/
  DESTINATION share/${PROJECT_NAME}/models
)

# Use ament_auto_package to automatically handle dependencies
ament_auto_package()
