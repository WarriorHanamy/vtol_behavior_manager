
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-c"]


RUN --mount=type=cache,target=/var/cache/apt \
    apt update && apt install -y \
    sudo \
    wget \
    python3-pip \
    ros-humble-plotjuggler-ros

# Install Python packages (ONNX Runtime)
RUN pip3 install --no-cache-dir onnxruntime numpy hydra-core

RUN useradd -m -u 1000 ros && \
    echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    echo "source /opt/ros/humble/setup.bash" >> /home/ros/.bashrc

RUN mkdir -p /home/ros/ros2_ws
RUN chown -R ros:ros /home/ros/ros2_ws

# Copy project files
COPY --chown=ros:ros src /home/ros/ros2_ws/src
COPY --chown=ros:ros scripts /home/ros/ros2_ws/scripts

USER ros
WORKDIR /home/ros/ros2_ws

# Set environment variables
ENV ROS_DISTRO=humble


RUN echo "source /home/ros/ros2_ws/install/setup.bash" >> \
    /home/ros/.bashrc

USER root
RUN --mount=type=cache,target=/var/cache/apt \
    apt install -y software-properties-common && \
    add-apt-repository ppa:maveonair/helix-editor && \
    apt update && \
    apt install -y helix && \
    echo "alias vim='hx'" >> /root/.bashrc
