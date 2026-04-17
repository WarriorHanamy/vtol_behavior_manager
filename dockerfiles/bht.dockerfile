# =============================================================
# BHT simulation/offload image (two-stage build)
#
# Stage 1 (builder): install deps, build ROS workspace
# Stage 2 (runtime): copy runtime artifacts for a lean image
#
# C++ colcon builds are orthogonal to Python/TensorRT validation.
# To test Python/TRT only, use the runtime stage directly.
# =============================================================

# ---------- Stage 1: builder ----------
FROM osrf/ros:humble-desktop AS builder
SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=cache,target=/var/cache/apt \
  --mount=type=cache,target=/var/lib/apt/lists \
  apt-get update && apt-get install -y --no-install-recommends \
  sudo \
  wget \
  curl \
  python3-pip \
  git

RUN useradd -m -u 1000 ros && \
  echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN mkdir -p /home/ros/ros2_ws/src && \
  chown -R ros:ros /home/ros/ros2_ws

USER ros
WORKDIR /home/ros/ros2_ws

# --- Python deps (needed for both builder and runtime) ---
RUN pip3 install --user --no-cache-dir \
  onnxruntime \
  numpy \
  hydra-core \
  tensorrt-cu12-libs \
  tensorrt-cu12-bindings \
  cuda-python

# --- ROS workspace build ---
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

# Layer 3: neural_executor (C++ node, most frequently changed)
COPY --chown=ros:ros src/neural_manager src/neural_manager
RUN source /opt/ros/humble/setup.bash && \
  source install/setup.bash && \
  colcon build --packages-select neural_executor

# ---------- Stage 2: runtime ----------
FROM osrf/ros:humble-desktop AS runtime
SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=humble
ENV WS_DIR=/home/ros/ros2_ws

RUN apt-get update && apt-get install -y --no-install-recommends \
  sudo \
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

# --- Python runtime deps (installed last, layer changes most) ---
RUN pip3 install --no-cache-dir \
  onnxruntime \
  numpy \
  hydra-core \
  tensorrt-cu12-libs \
  tensorrt-cu12-bindings \
  cuda-python

RUN useradd -m -u 1000 ros && \
  echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
  mkdir -p ${WS_DIR}/src && \
  chown -R ros:ros ${WS_DIR}

# Copy compiled ROS artifacts from builder
COPY --from=builder --chown=ros:ros ${WS_DIR}/install ${WS_DIR}/install

# Copy neural_inference source (not packaged as installable Python/ROS package)
COPY --from=builder --chown=ros:ros ${WS_DIR}/src/neural_manager/neural_inference ${WS_DIR}/src/neural_manager/neural_inference

# Copy engine file into image
COPY --chown=ros:ros src/neural_manager/neural_inference/vtol_hover.fp16.engine /home/ros/vtol_hover.fp16.engine

# Set PYTHONPATH so python -m neural_manager.neural_inference.neural_infer works
ENV PYTHONPATH=${WS_DIR}/src:${WS_DIR}/install/lib/python3.10/site-packages:/opt/ros/humble/lib/python3.10/site-packages

# Copy entrypoint
COPY dockerfiles/bht_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER ros
WORKDIR ${WS_DIR}

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
