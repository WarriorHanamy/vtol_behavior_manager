
#
# PX4 Gazebo 8 (Harmonic) - PX4 source and build layer
#
FROM px4_deps

LABEL maintainer="WarriorHanamy <rongerch@outlook.com>"

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

ENV PATH="/home/px4/PX4-Neupilot/Tools:$PATH"

CMD bash
