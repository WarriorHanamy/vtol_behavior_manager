#!/bin/bash
# Run ROS2 development container (detached mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

docker run --rm \
    --privileged --net=host \
    -itd \
    -w /home/ros/ros2_ws \
    -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
    -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
    -v "$HOME/.Xauthority:/home/ros/.Xauthority" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "${PROJECT_ROOT}/src:/home/ros/ros2_ws/src" \
    -v "${PROJECT_ROOT}/scripts:/home/ros/ros2_ws/scripts" \
    -v "${PROJECT_ROOT}/justfile:/home/ros/ros2_ws/justfile" \
    --name ros2 \
    ros2
