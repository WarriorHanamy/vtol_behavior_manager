# 同时声明大小写 ARG
ARG http_proxy=http://172.17.0.1:7890
ARG HTTP_PROXY=${http_proxy}
ARG https_proxy=${http_proxy}
ARG HTTPS_PROXY=${http_proxy}
ARG no_proxy=localhost,127.0.0.1
ARG NO_PROXY=${no_proxy}

FROM osrf/ros:humble-desktop

# 声明 ARG 以便在后续使用
ARG http_proxy
ARG HTTP_PROXY
ARG https_proxy
ARG HTTPS_PROXY
ARG no_proxy
ARG NO_PROXY
SHELL ["/bin/bash", "-c"]


RUN apt update && \
    apt install -y gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl \
    libfuse2 fuse libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor-dev



WORKDIR /app

RUN curl -L -O https://github.com/mavlink/qgroundcontrol/releases/download/v5.0.8/QGroundControl-x86_64.AppImage

RUN chmod +x QGroundControl-x86_64.AppImage
RUN groupadd -r qgc && useradd -m -g qgc -u 1000 qgc
RUN ln -s /app/QGroundControl-x86_64.AppImage /usr/local/bin/qgc
RUN chown -R qgc:qgc /app

RUN apt install -y software-properties-common && \
    add-apt-repository ppa:maveonair/helix-editor && \
    apt update && \
    apt install -y helix && \
    echo "alias vim='hx'" >> /root/.bashrc

USER qgc
WORKDIR /home/qgc
COPY ./QGroundControl.ini /home/qgc/.config/QGroundControl/QGroundControl.ini
RUN mkdir ulgs/
RUN chmod 777 ulgs/
