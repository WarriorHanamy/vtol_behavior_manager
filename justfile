set shell := ["bash", "-c"]

example:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    ros2 run example_mode_manual_cpp example_mode_manual

neural-mode:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    ros2 launch neural_executor neural_demo.launch.py

neural-inference:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    ros2 launch neural_pos_ctrl pos_ctrl_launch.py

fake-network:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    ros2 launch fake_network fake_network_node.launch.py

config-px4msg:
    bash {{justfile_directory()}}/scripts/config_px4msg.sh

build:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    colcon build --symlink-install \
    --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

alias b := full-build
full-build:
    just config-px4msg && \
    just build

alias c := clean
clean:
    [ -d {{justfile_directory()}}/build ] && rm -rf {{justfile_directory()}}/build; [ -d {{justfile_directory()}}/log ] && rm -rf {{justfile_directory()}}/log; [ -d {{justfile_directory()}}/install ] && rm -rf {{justfile_directory()}}/install

build-qgc:
    docker build -f docker/qgc5.dockerfile \
    --network=host \
    -t qgc5:latest .

build-ros2:
    docker build -f docker/ros2.dockerfile \
    --network=host \
    -t ros2:latest .

run-qgc:
    echo " " | sudo -S chmod 777 /dev/input/event* && \
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

build-px4:
    bash {{justfile_directory()}}/scripts/build_px4_gazebo.sh

run-px4:
    docker run -it --gpus all \
        --rm \
        --entrypoint bash \
        --privileged --network host \
        -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
        -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
        -v $HOME/.Xauthority:/root/.Xauthority \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        --name px4-gazebo-harmonic-tmp \
        px4-gazebo-harmonic:v1

enter-px4:
    docker exec -it px4-gazebo-harmonic-tmp /bin/bash

clean-px4:
    docker rm -f px4-gazebo-harmonic-tmp

df-docker:
    docker system df

# attach
alias a := enter-ros2
enter-ros2:
    docker exec -it ros2 bash

# Docker Compose commands
up:
    docker compose up -d

down:
    docker compose down

dc-restart:
    docker compose restart
