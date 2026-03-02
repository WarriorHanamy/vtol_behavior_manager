#!/bin/bash
# Neural executor demo launcher

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source ROS2 and workspace setup
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source "${PROJECT_ROOT}/install/setup.sh"

# Launch neural demo
ros2 launch neural_executor neural_demo.launch.py
