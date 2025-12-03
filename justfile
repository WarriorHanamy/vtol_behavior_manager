set shell := ["bash", "-c"]

example:
    source ./install/setup.sh && \
    ros2 run example_mode_manual_cpp example_mode_manual

neural-mode:
    source ./install/setup.sh && \
    ros2 launch neural_demo neural_demo.launch.py

neural-inference:
    source ./install/setup.sh && \
    ros2 launch isaac_pos_ctrl_neural isaac_pos_ctrl_launch.py

fake-network:
    source ./install/setup.sh && \
    ros2 launch neural_demo fake_network_node.launch.py

config-px4msg:
    bash ./scripts/config_px4msg.sh

build:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    colcon build --symlink-install \
    --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3

alias b := full-build
full-build:
    just config-px4msg && \
    just build

alias c := clean
clean:
    [ -d build ] && rm -rf build; [ -d log ] && rm -rf log; [ -d install ] && rm -rf install

build-qgc:
    docker build -f docker/qgc5.dockerfile \
    --network=host \
    -t qgc5:latest .

build-ros2:
    docker build -f docker/ros2.dockerfile \
    --network=host \
    -t ros2:latest .

run-qgc:
    docker run --rm \
        --privileged --net=host \
        -it \
        -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
        -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
        -v $HOME/.Xauthority:/home/qgc/.Xauthority \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        --name qgc5 \
        qgc5 qgc

run-ros2:
    docker run --rm \
        --privileged --net=host \
        -it \
        -w /home/ros/ros2_ws \
        -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
        -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
        -v $HOME/.Xauthority:/home/ros/.Xauthority \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v {{justfile_directory()}}:/home/ros/ros2_ws \
        --name ros2 \
        ros2

# attach
alias a := enter-ros2
enter-ros2:
    docker exec -it ros2 bash


# Docker Compose commands
up:
    docker compose up

down:
    docker compose down

dc-restart:
    docker compose restart
