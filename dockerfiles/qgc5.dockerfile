FROM qgc_deps

ARG QGC_VERSION=5.0.8

WORKDIR /app

RUN curl -L -o QGroundControl-x86_64.AppImage \
    "https://github.com/mavlink/qgroundcontrol/releases/download/v${QGC_VERSION}/QGroundControl-x86_64.AppImage"

RUN chmod +x QGroundControl-x86_64.AppImage && \
    ./QGroundControl-x86_64.AppImage --appimage-extract && \
    rm QGroundControl-x86_64.AppImage && \
    groupadd -r qgc && \
    useradd -m -g qgc -u 1000 qgc && \
    ln -s /app/squashfs-root/AppRun /usr/local/bin/qgc && \
    mkdir -p /home/qgc/.config/QGroundControl /home/qgc/ulgs && \
    chown -R qgc:qgc /app /home/qgc

COPY ./dockerfiles/assets/QGroundControl.ini /home/qgc/.config/QGroundControl/QGroundControl.ini
RUN chown qgc:qgc /home/qgc/.config/QGroundControl/QGroundControl.ini

USER qgc
WORKDIR /home/qgc

CMD ["qgc"]
