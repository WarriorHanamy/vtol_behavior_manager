# =============================================================
# BHT prep image for Jetson deployment (two-stage build)
#
# This Dockerfile intentionally stops before any native compilation.
# It is safe to build on the host with buildx (ARM64) and then hand
# off to a Jetson-native Docker build for colcon compilation.
#
# Pattern: Follows linker/dockerfiles/ros2.prep.Dockerfile convention
# =============================================================

FROM ros:humble-ros-base AS prep

ARG UBUNTU_PORTS_MIRROR=http://mirrors.ustc.edu.cn/ubuntu-ports
ARG ROS_MIRROR=https://mirrors.ustc.edu.cn/ros2/ubuntu

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV WS_DIR=/root/ros2_ws

# Use mirror for faster apt operations
RUN sed -i "s|http://ports.ubuntu.com/ubuntu-ports|${UBUNTU_PORTS_MIRROR}|g" /etc/apt/sources.list && \
    sed -i "s|http://packages.ros.org/ros2/ubuntu|${ROS_MIRROR}|g" /etc/apt/sources.list.d/ros2.sources && \
    sed -i "s|Types: deb deb-src|Types: deb|g" /etc/apt/sources.list.d/ros2.sources

# System dependencies (no compilation here)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git \
    python3-rosdep python3-pip \
    libeigen3-dev libpcl-dev libssl-dev

# ROS dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-pcl-ros ros-humble-pcl-conversions \
    ros-humble-tf2 ros-humble-tf2-ros ros-humble-tf2-sensor-msgs \
    ros-humble-tf2-geometry-msgs ros-humble-tf2-eigen \
    ros-humble-eigen3-cmake-module

# Initialize rosdep
RUN rosdep init || echo "rosdep already initialized" && \
    rosdep update || rosdep update || true

# Prepare workspace
WORKDIR ${WS_DIR}/src

# Copy source code (no compilation in prep stage)
COPY src/px4_msgs ./px4_msgs
COPY src/px4-ros2-interface-lib ./px4-ros2-interface-lib
COPY src/neural_manager ./neural_manager

# Fix px4_msgs versioned messages (same as simulation Dockerfile)
RUN cp -r px4_msgs/msg/versioned/* px4_msgs/msg/ || true

WORKDIR ${WS_DIR}
SHELL ["/bin/bash", "-c"]