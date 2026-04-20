#!/bin/bash
set -e

# ROS2 setup.bash references unbound variables (e.g. AMENT_TRACE_SETUP_FILES).
# Temporarily disable nounset around sourcing to avoid "unbound variable" errors.
set +u
source /opt/ros/humble/setup.bash
source /home/ros/ros2_ws/install/setup.bash
set -u

exec "$@"
