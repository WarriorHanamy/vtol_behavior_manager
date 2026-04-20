# =============================================================
# BHT native image for Jetson deployment (single-stage build)
#
# This Dockerfile performs dependency installation and native
# colcon compilation in a single stage for simplicity.
# =============================================================

#########################
# Global build arguments #
#########################
ARG BASE_IMAGE=nvcr.io/nvidia/l4t-jetpack
ARG JETPACK_TAG=r36.4.0
FROM ${BASE_IMAGE}:${JETPACK_TAG}
SHELL ["/bin/bash", "-c"]

ARG UBUNTU_PORTS_MIRROR=http://mirrors.ustc.edu.cn/ubuntu-ports
ARG ROS_MIRROR=https://mirrors.ustc.edu.cn/ros2/ubuntu

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

RUN --mount=type=cache,target=/var/cache/apt \
  --mount=type=cache,target=/var/lib/apt/lists \
  apt-get update && apt-get install -y --no-install-recommends \
  curl \
  gnupg2 \
  lsb-release \
  locales \
  software-properties-common \
  && locale-gen en_US en_US.UTF-8 \
  && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8

RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | apt-key add - && \
  echo "deb http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" > /etc/apt/sources.list.d/ros2.list

# Use mirror for faster apt operations
RUN sed -i "s|http://ports.ubuntu.com/ubuntu-ports|${UBUNTU_PORTS_MIRROR}|g" /etc/apt/sources.list && \
  sed -i "s|http://packages.ros.org/ros2/ubuntu|${ROS_MIRROR}|g" /etc/apt/sources.list.d/ros2.list && \
  sed -i "s|Types: deb deb-src|Types: deb|g" /etc/apt/sources.list.d/ros2.list || true


# Update package list
RUN --mount=type=cache,target=/var/cache/apt \
  --mount=type=cache,target=/var/lib/apt/lists \
  apt-get update

# Basic development tools
RUN --mount=type=cache,target=/var/cache/apt \
  --mount=type=cache,target=/var/lib/apt/lists \
  apt-get install -y --no-install-recommends \
  build-essential \
  cmake \
  git \
  wget \
  sudo \
  python3-pip

# ROS2 core packages
RUN --mount=type=cache,target=/var/cache/apt \
  --mount=type=cache,target=/var/lib/apt/lists \
  apt-get install -y --no-install-recommends \
  ros-humble-ros-base \
  python3-colcon-common-extensions \
  python3-rosdep

# FastRTPS
RUN --mount=type=cache,target=/var/cache/apt \
  --mount=type=cache,target=/var/lib/apt/lists \
  apt-get install -y --no-install-recommends \
  ros-humble-rmw-fastrtps-cpp

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV WS_DIR=/home/ros/ros2_ws

# Initialize rosdep
RUN rosdep init || echo "rosdep already initialized" && \
  rosdep update || rosdep update || true

# Prepare workspace
RUN mkdir -p ${WS_DIR}/src && \
  useradd -m -u 1000 ros || true
WORKDIR ${WS_DIR}/src

# Copy source code
COPY --chown=ros:ros src/px4_msgs ./px4_msgs
COPY --chown=ros:ros src/px4-ros2-interface-lib ./px4-ros2-interface-lib
COPY --chown=ros:ros src/neural_manager ./neural_manager
# Fix px4_msgs versioned messages
RUN cp -r px4_msgs/msg/versioned/* px4_msgs/msg/ || true


WORKDIR ${WS_DIR}

# Compile ROS packages natively
RUN source /opt/ros/humble/setup.bash && \
  colcon build \
  --packages-select px4_msgs px4_ros2_cpp\
  --parallel-workers 4

# Compile ROS packages natively
RUN source /opt/ros/humble/setup.bash && \
  colcon build \
  --packages-select neural_executor \
  --parallel-workers 4 \
  --symlink-install && \
  test -f install/setup.bash || (echo "ERROR: install/setup.bash not found" && ls -la && exit 1)


# Python runtime packages (required by neural_manager)
RUN pip3 install --no-cache-dir --user onnxruntime numpy hydra-core
RUN pip3 install --no-cache-dir --user cuda-python==12.6.* cuda-bindings==12.9.*

# Setup user environment
USER ros
WORKDIR ${WS_DIR}
# Copy entrypoint script
COPY --chmod=755 dockerfiles/bht_entrypoint.sh /entrypoint.sh

# Set PYTHONPATH for module-style execution
# Includes both installed packages and workspace source directories
ENV PYTHONPATH=${WS_DIR}/install/lib/python3.10/site-packages:${WS_DIR}/src:${WS_DIR}/src/neural_executor:${PYTHONPATH}

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
