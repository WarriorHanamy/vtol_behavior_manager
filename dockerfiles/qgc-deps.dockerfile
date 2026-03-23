FROM ubuntu:22.04

ARG APT_MIRROR=mirrors.tuna.tsinghua.edu.cn

ENV DEBIAN_FRONTEND=noninteractive
ENV QT_X11_NO_MITSHM=1

RUN sed -i "s@archive.ubuntu.com@${APT_MIRROR}@g; s@security.ubuntu.com@${APT_MIRROR}@g" /etc/apt/sources.list

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && \
    apt-get -y --quiet --no-install-recommends install \
        ca-certificates \
        curl \
        fuse \
        gstreamer1.0-gl \
        gstreamer1.0-libav \
        gstreamer1.0-plugins-bad \
        libfuse2 \
        libopengl0 \
        libxcb-cursor-dev \
        libxcb-xinerama0 \
        libxkbcommon-x11-0
