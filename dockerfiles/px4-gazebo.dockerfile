
#
# PX4 Gazebo 8 (Harmonic) development environment in Ubuntu 22.04 Jammy
#
FROM px4io/px4-dev-base-jammy:2024-05-18

# Original author: Steven Cheng <zhenghw23@foxmail.com> (Arclunar)
LABEL maintainer="WarriorHanamy <rongerch@outlook.com>"

# Some QT-Apps/Gazebo don't not show controls without this
ENV QT_X11_NO_MITSHM=1

RUN sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get -y --quiet --no-install-recommends install \
        ant \
        binutils \
        bc \
        dirmngr \
        dmidecode \
        pkg-config \
        libimage-exiftool-perl \
        libxml2-utils \
        mesa-utils \
        protobuf-compiler \
        x-window-system


RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update && apt install -y \
    vim \
    python3-pip python3-venv \
    curl lsb-release gnupg wget \
    sudo

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
 	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null \
 	&& apt-get update \
 	&& DEBIAN_FRONTEND=noninteractive apt-get -y --quiet --no-install-recommends install \
 		ant \
 		binutils \
 		bc \
 		dirmngr \
        dmidecode \
 		gz-harmonic \
        libunwind-dev \
        gstreamer1.0-libav \
 		pkg-config \
 		gstreamer1.0-plugins-bad \
 		gstreamer1.0-plugins-base \
 		gstreamer1.0-plugins-good \
 		gstreamer1.0-plugins-ugly \
 		libeigen3-dev \
 		libgstreamer-plugins-base1.0-dev \
 		libimage-exiftool-perl \
 		libopencv-dev \
 		libxml2-utils \
 		mesa-utils \
 		protobuf-compiler \
 		x-window-system

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y --quiet --no-install-recommends install \
    libprotobuf-dev

WORKDIR /home/px4
ARG PX4_GIT_REF=main
RUN git clone --recursive --branch "${PX4_GIT_REF}" --depth 1 \
    https://github.com/WarriorHanamy/PX4-Neupilot.git

WORKDIR /home/px4/PX4-Neupilot
RUN bash install-dds-agent.bash

RUN useradd -m -s /bin/bash px4 && \
    echo "px4 ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/px4 && \
    chmod 0440 /etc/sudoers.d/px4 && \
    chown -R px4:px4 /home/px4


ENV GZ_DISTRO=harmonic
ENV GIT_SUBMODULES_ARE_EVIL=1

USER px4
WORKDIR /home/px4/PX4-Neupilot
RUN HEADLESS=1 bash -c "make px4_sitl_default"
RUN HEADLESS=1 timeout 120 bash -c "make px4_sitl_default gazebo"; exit_code=$$?;  exit 0


#RUN make px4_sitl_default
ENV PATH="/home/px4/PX4-Neupilot/Tools:$PATH"

CMD bash
