#!/bin/bash
# Run ROS2 workspace in Docker using Podman

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

podman run --rm \
    --privileged --net=host --ipc=host \
    -it \
    --security-opt label=disable \
    --userns=keep-id \
    -w /home/ros/ros2_ws \
    -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
    -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
    -v "$HOME/.Xauthority:/home/ros/.Xauthority:Z" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:Z \
    -v "${PROJECT_ROOT}/src:/home/ros/ros2_ws/src:Z" \
    -v "${PROJECT_ROOT}/scripts:/home/ros/ros2_ws/scripts:Z" \
    -v "${PROJECT_ROOT}/justfile:/home/ros/ros2_ws/justfile:Z" \
    --name ros2-vtol \
    ros2-vtol
