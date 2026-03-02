#!/bin/bash
# Run QGroundControl in Docker

set -e

# Ensure input device permissions
echo "" | sudo -S chmod 777 /dev/input/event*

docker run --rm \
    --privileged --net=host \
    -it \
    -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
    -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
    -v "$HOME/.Xauthority:/home/qgc/.Xauthority" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    --name qgc5 \
    qgc5 qgc
