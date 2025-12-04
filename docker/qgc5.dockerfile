
FROM osrf/ros:humble-desktop
SHELL ["/bin/bash", "-c"]

RUN apt update

RUN apt-get remove modemmanager -y \
    && apt install -y gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl \
    libfuse2 fuse libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor-dev



WORKDIR /app

RUN curl -L -O https://github.com/mavlink/qgroundcontrol/releases/download/v5.0.8/QGroundControl-x86_64.AppImage

RUN chmod +x QGroundControl-x86_64.AppImage
RUN groupadd -r qgc && useradd -m -g qgc -u 1000 qgc
RUN ln -s /app/QGroundControl-x86_64.AppImage /usr/local/bin/qgc
RUN chown -R qgc:qgc /app

USER qgc
WORKDIR /home/qgc
COPY ./QGroundControl.ini /home/qgc/.config/QGroundControl/QGroundControl.ini
RUN mkdir ulgs/
RUN chmod 777 ulgs/
