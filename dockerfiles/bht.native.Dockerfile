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
ENV WS_DIR=/home/ros/ros2_ws

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

ENV ROS_DISTRO=humble
ENV WS_DIR=/home/ros/ros2_ws
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV PYTHONPATH=${WS_DIR}/src:/opt/ros/humble/lib/python3.10/site-packages:${PYTHONPATH}

# Create ros user (same UID as simulation for consistency)
RUN useradd -m -u 1000 ros && \
    echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p ${WS_DIR}/src && \
    chown -R ros:ros ${WS_DIR}

# Copy compiled artifacts and source from native-build stage
COPY --from=native-build ${WS_DIR}/install ${WS_DIR}/install
COPY --from=native-build ${WS_DIR}/src/px4_msgs ${WS_DIR}/src/px4_msgs
COPY --from=native-build ${WS_DIR}/src/px4-ros2-interface-lib ${WS_DIR}/src/px4-ros2-interface-lib
COPY --from=native-build ${WS_DIR}/src/neural_manager ${WS_DIR}/src/neural_manager

USER ros
WORKDIR ${WS_DIR}

# Copy entrypoint script
COPY --chmod=755 dockerfiles/bht_entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
