
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-c"]

COPY dockerfiles/bht_entrypoint.sh /entrypoint.sh
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


RUN pip3 install --no-cache-dir onnxruntime numpy hydra-core

RUN useradd -m -u 1000 ros && \
  echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/ros/ros2_ws/src
RUN chown -R ros:ros /home/ros/ros2_ws

USER ros
WORKDIR /home/ros/ros2_ws

# Layer 1: px4_msgs (least frequently changed)
COPY --chown=ros:ros src/px4_msgs src/px4_msgs
RUN cp -r src/px4_msgs/msg/versioned/* src/px4_msgs/msg/ && \
  source /opt/ros/humble/setup.bash && \
  colcon build --packages-select px4_msgs

# Layer 2: px4-ros2-interface-lib (medium frequency)
COPY --chown=ros:ros src/px4-ros2-interface-lib src/px4-ros2-interface-lib
RUN source /opt/ros/humble/setup.bash && \
  source install/setup.bash && \
  colcon build --packages-select px4_ros2_cpp

# Layer 3: neural_manager (most frequently changed)
COPY --chown=ros:ros src/neural_manager src/neural_manager
RUN source /opt/ros/humble/setup.bash && \
  source install/setup.bash && \
  colcon build --packages-select neural_executor

ENV ROS_DISTRO=humble

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
