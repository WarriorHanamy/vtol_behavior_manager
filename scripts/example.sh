#!/bin/bash
# ROS2 example mode - runs the C++ example node

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source ROS2 and workspace setup
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source "${PROJECT_ROOT}/install/setup.sh"

# Run the example node
ros2 run example_mode_manual_cpp example_mode_manual
