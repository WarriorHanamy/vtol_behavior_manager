# =============================================================
# BHT simulation/offload image (two-stage build)
#
# Stage 1 (builder): install deps, build ROS workspace
# Stage 2 (runtime): copy runtime artifacts for a lean image
#
# C++ colcon builds are orthogonal to Python/TensorRT validation.
# To test Python/TRT only, use the runtime stage directly.
# =============================================================

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

# Layer 2: goal_msgs (depended on by neural_gate)
COPY --chown=ros:ros src/goal_msgs src/goal_msgs
RUN source /opt/ros/humble/setup.bash && \
  source install/setup.bash && \
  colcon build --packages-select goal_msgs

# Layer 3: neural_gate (most frequently changed)
COPY --chown=ros:ros src/neural_manager src/neural_manager
RUN source /opt/ros/humble/setup.bash && \
  source install/setup.bash && \
  colcon build --packages-select neural_gate

ENV ROS_DISTRO=humble

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
