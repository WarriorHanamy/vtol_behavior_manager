#!/bin/bash
# Run PX4 Gazebo simulation with specified model

set -e

# Default model
MODEL="${1:-2}"

docker run -it --gpus all \
    --rm \
    --privileged --network host \
    -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
    -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
    -v "$HOME/.Xauthority:/root/.Xauthority" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    --name px4-gazebo-harmonic-tmp \
    px4-gazebo-harmonic:v1 \
    /bin/bash -c "source ~/.bashrc && runsim.sh ${MODEL}"
