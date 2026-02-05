
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-c"]

RUN --mount=type=cache,target=/var/cache/apt \
    apt update && apt install -y \
    sudo \
    wget \
    python3-pip \
    ros-humble-plotjuggler-ros

# Install just command runner from GitHub releases
RUN wget https://github.com/casey/just/releases/download/1.36.0/just-1.36.0-x86_64-unknown-linux-musl.tar.gz && \
    tar -xzf just-1.36.0-x86_64-unknown-linux-musl.tar.gz && \
    mv just /usr/local/bin/ && \
    rm just-1.36.0-x86_64-unknown-linux-musl.tar.gz && \
    chmod +x /usr/local/bin/just

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
COPY --chown=ros:ros justfile /home/ros/ros2_ws/justfile

USER ros
WORKDIR /home/ros/ros2_ws

# Set environment variables
ENV ROS_DISTRO=humble

# Execute just b command (full build)
ARG LATETST=true
RUN just b

RUN echo "source /home/ros/ros2_ws/install/setup.bash" >> \
    /home/ros/.bashrc

RUN echo "alias j='just'" >> /home/ros/.bashrc
ENV INFER_WORKSPACE=/home/ros/ros2_ws
