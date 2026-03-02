#!/bin/bash
# Build the ROS2 workspace

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Config px4msgs
cp "${PROJECT_ROOT}/src/px4_msgs/msg/versioned/"* "${PROJECT_ROOT}/src/px4_msgs/msg/"

# Source ROS2 setup
source "/opt/ros/${ROS_DISTRO}/setup.bash"

# Build with symlink install and compile commands export
colcon build --symlink-install \
    --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
