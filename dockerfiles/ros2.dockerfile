
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-c"]

COPY dockerfiles/ros2_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    wget \
    curl \
    python3-pip \
    iproute2 \
    iputils-ping \
    net-tools \
    dnsutils \
    traceroute \
    mtr \
    nmap \
    tcpdump \
    telnet \
    netcat \
    iperf3 \
    ethtool \
    bridge-utils \
    rsync \
    git \
    vim \
    nano \
    tmux \
    htop


RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-plotjuggler-ros

RUN pip3 install --no-cache-dir onnxruntime numpy hydra-core

RUN useradd -m -u 1000 ros && \
    echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/ros/ros2_ws
RUN chown -R ros:ros /home/ros/ros2_ws

COPY --chown=ros:ros src /home/ros/ros2_ws/src

USER ros
WORKDIR /home/ros/ros2_ws

RUN cp -r src/px4_msgs/msg/versioned/* src/px4_msgs/msg/
RUN source /opt/ros/humble/setup.bash && colcon build

ENV ROS_DISTRO=humble

USER root
RUN --mount=type=cache,target=/var/cache/apt \
    apt install -y software-properties-common && \
    add-apt-repository ppa:maveonair/helix-editor && \
    apt update && \
    apt install -y helix && \
    echo "alias vim='hx'" >> /root/.bashrc

USER ros
ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
