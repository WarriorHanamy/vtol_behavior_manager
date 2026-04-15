# =============================================================
# BHT native image for Jetson deployment (two-stage build)
#
# This Dockerfile runs on a Jetson-native Docker daemon and resumes
# from a prep image built elsewhere. It performs the final colcon
# compilation to produce the deployable image.
#
# Pattern: Follows linker/dockerfiles/ros2.native.Dockerfile convention
# =============================================================

ARG PREP_IMAGE
FROM ${PREP_IMAGE} AS native-build

ENV ROS_DISTRO=humble
ENV WS_DIR=/root/ros2_ws

WORKDIR ${WS_DIR}
SHELL ["/bin/bash", "-c"]

# Compile ROS packages natively on Jetson
RUN source /opt/ros/humble/setup.bash && \
    colcon build \
    --packages-select px4_msgs px4_ros2_cpp neural_executor \
    --parallel-workers 4

# =============================================================
# Final lightweight runtime image
# =============================================================
FROM ros:humble-ros-base

ARG UBUNTU_PORTS_MIRROR=http://mirrors.ustc.edu.cn/ubuntu-ports
ARG ROS_MIRROR=https://mirrors.ustc.edu.cn/ros2/ubuntu

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV WS_DIR=/root/ros2_ws
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV PYTHONPATH=${WS_DIR}/src:/opt/ros/humble/lib/python3.10/site-packages:${PYTHONPATH}

# Use mirror for faster apt operations
RUN sed -i "s|http://ports.ubuntu.com/ubuntu-ports|${UBUNTU_PORTS_MIRROR}|g" /etc/apt/sources.list && \
    sed -i "s|http://packages.ros.org/ros2/ubuntu|${ROS_MIRROR}|g" /etc/apt/sources.list.d/ros2.sources && \
    sed -i "s|Types: deb deb-src|Types: deb|g" /etc/apt/sources.list.d/ros2.sources

# Runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    libflann1.9 \
    ros-humble-pcl-ros ros-humble-pcl-conversions \
    ros-humble-tf2 ros-humble-tf2-ros ros-humble-tf2-sensor-msgs \
    ros-humble-tf2-geometry-msgs ros-humble-tf2-eigen && \
    rm -rf /var/lib/apt/lists/*

# Copy compiled artifacts and source from native-build stage
COPY --from=native-build ${WS_DIR}/install ${WS_DIR}/install
COPY --from=native-build ${WS_DIR}/src/px4_msgs ${WS_DIR}/src/px4_msgs
COPY --from=native-build ${WS_DIR}/src/px4-ros2-interface-lib ${WS_DIR}/src/px4-ros2-interface-lib
COPY --from=native-build ${WS_DIR}/src/neural_manager ${WS_DIR}/src/neural_manager

# Create ros user (same UID as simulation for consistency)
RUN useradd -m -u 1000 ros && \
    echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    chown -R ros:ros ${WS_DIR}

USER ros
WORKDIR ${WS_DIR}

# Copy entrypoint script before runtime user takes over.
COPY --chmod=755 dockerfiles/bht_entrypoint.sh /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
