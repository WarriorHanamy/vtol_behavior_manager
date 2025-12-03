
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-c"]

RUN --mount=type=cache,target=/var/cache/apt \
    apt update && apt install -y \
    sudo \
    wget \
    python3-pip \
    ros-humble-plotjuggler-ros

# Install just command runner
RUN wget -qO - 'https://proget.makedeb.org/debian-feeds/prebuilt-mpr.pub' | gpg --dearmor | tee /usr/share/keyrings/prebuilt-mpr-archive-keyring.gpg 1> /dev/null && \
    echo "deb [arch=all,$(dpkg --print-architecture) signed-by=/usr/share/keyrings/prebuilt-mpr-archive-keyring.gpg] https://proget.makedeb.org prebuilt-mpr $(lsb_release -cs)" | tee /etc/apt/sources.list.d/prebuilt-mpr.list && \
    apt update && \
    apt install -y just
    

# Install Python packages (ONNX Runtime)
RUN pip3 install --no-cache-dir onnxruntime numpy

RUN useradd -m -u 1000 ros && \
    echo "ros ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers \
    echo "source /opt/ros/humble/setup.bash" >> ${HOME}/.bashrc


USER ros
WORKDIR /home/ros
RUN mkdir trash_bin
