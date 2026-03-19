FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update && \
    apt install -y curl gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl \
    libfuse2 fuse libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor-dev



WORKDIR /app

RUN curl -L -O https://github.com/mavlink/qgroundcontrol/releases/download/v5.0.8/QGroundControl-x86_64.AppImage

RUN chmod +x QGroundControl-x86_64.AppImage && \
    ./QGroundControl-x86_64.AppImage --appimage-extract && \
    rm QGroundControl-x86_64.AppImage && \
    groupadd -r qgc && useradd -m -g qgc -u 1000 qgc && \
    ln -s /app/squashfs-root/AppRun /usr/local/bin/qgc && \
    chown -R qgc:qgc /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update && apt install -y libopengl0

USER qgc
WORKDIR /home/qgc
COPY ./dockerfiles/assets/QGroundControl.ini /home/qgc/.config/QGroundControl/QGroundControl.ini
RUN mkdir ulgs/
RUN chmod 777 ulgs/
CMD qgc