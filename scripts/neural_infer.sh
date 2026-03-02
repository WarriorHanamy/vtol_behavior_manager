#!/bin/bash
# Neural inference runner

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source ROS2 setup
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source "${PROJECT_ROOT}/install/setup.sh"

# Run neural inference
python3 "${PROJECT_ROOT}/src/neural_manager/neural_pos_ctrl/neural_infer.py"
