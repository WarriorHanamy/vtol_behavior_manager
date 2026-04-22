
#
# PX4 Gazebo 8 (Harmonic) - PX4 source and build layer
#
FROM px4_deps

LABEL maintainer="WarriorHanamy <rongerch@outlook.com>"

WORKDIR /home/px4
ARG PX4_GIT_URL=https://github.com/WarriorHanamy/PX4-Neupilot.git
ARG PX4_GIT_REF=main
RUN useradd -M -d /home/px4 -s /bin/bash px4 \
  && install -d -o px4 -g px4 /home/px4 /home/px4/.cache /home/px4/.cache/ccache \
  && echo "px4 ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/px4 \
  && chmod 0440 /etc/sudoers.d/px4
RUN git clone --depth 1 --branch "${PX4_GIT_REF}" "${PX4_GIT_URL}" /home/px4/PX4-Neupilot --recursive

WORKDIR /home/px4/PX4-Neupilot
RUN bash install-dds-agent.bash

RUN git -C /home/px4/PX4-Neupilot submodule sync --recursive \
  && git -C /home/px4/PX4-Neupilot submodule update --init --recursive --jobs=8

RUN chown -R px4:px4 /home/px4/PX4-Neupilot


ENV GZ_DISTRO=harmonic
ENV GIT_SUBMODULES_ARE_EVIL=1

USER px4
WORKDIR /home/px4/PX4-Neupilot
RUN HEADLESS=1 bash -c "make px4_sitl_default"
RUN HEADLESS=1 timeout 120 bash -c "make px4_sitl_default gazebo"; exit_code=$$?;  exit 0

ENV PATH="/home/px4/PX4-Neupilot/Tools:$PATH"

CMD bash
