set shell := ["bash", "-c"]
export PATH := "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:~/.cargo/bin"

example:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    ros2 run example_mode_manual_cpp example_mode_manual

neural-mode:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    ros2 launch neural_executor neural_demo.launch.py

neural-infer:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    source {{justfile_directory()}}/install/setup.sh && \
    python3 src/neural_manager/neural_pos_ctrl/neural_infer.py

config-px4msgs:
    bash {{justfile_directory()}}/scripts/config_px4msgs.sh

build:
    source /opt/ros/${ROS_DISTRO}/setup.bash && \
    colcon build --symlink-install \
    --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

alias b := full-build
full-build:
    just config-px4msgs && \
    just build

alias c := clean
clean:
    [ -d {{justfile_directory()}}/build ] && rm -rf {{justfile_directory()}}/build; [ -d {{justfile_directory()}}/log ] && rm -rf {{justfile_directory()}}/log; [ -d {{justfile_directory()}}/install ] && rm -rf {{justfile_directory()}}/install

build-qgc:
    docker build \
    --build-arg http_proxy=http://172.17.0.1:7890 \
    --build-arg https_proxy=http://172.17.0.1:7890 \
    --build-arg HTTP_PROXY=http://172.17.0.1:7890 \
    --build-arg HTTPS_PROXY=http://172.17.0.1:7890 \
    --build-arg no_proxy=localhost,127.0.0.1 \
    --build-arg NO_PROXY=localhost,127.0.0.1 \
    -f docker/qgc5.dockerfile \
    -t qgc5:latest .

build-ros2:
    docker build \
    --build-arg http_proxy=http://172.17.0.1:7890 \
    --build-arg https_proxy=http://172.17.0.1:7890 \
    --build-arg HTTP_PROXY=http://172.17.0.1:7890 \
    --build-arg HTTPS_PROXY=http://172.17.0.1:7890 \
    --build-arg no_proxy=localhost,127.0.0.1 \
    --build-arg NO_PROXY=localhost,127.0.0.1 \
    -f docker/ros2.dockerfile \
    -t ros2-vtol:latest .

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
        -v {{justfile_directory()}}/src:/home/ros/ros2_ws/src \
        -v {{justfile_directory()}}/scripts:/home/ros/ros2_ws/scripts \
        -v {{justfile_directory()}}/justfile:/home/ros/ros2_ws/justfile \
        --name ros2-vtol \
        ros2-vtol

build-px4:
    docker build \
    --build-arg http_proxy=http://172.17.0.1:7890 \
    --build-arg https_proxy=http://172.17.0.1:7890 \
    --build-arg HTTP_PROXY=http://172.17.0.1:7890 \
    --build-arg HTTPS_PROXY=http://172.17.0.1:7890 \
    --build-arg no_proxy=localhost,127.0.0.1 \
    --build-arg NO_PROXY=localhost,127.0.0.1 \
    -f docker/px4-gazebo.dockerfile \
    -t px4-gazebo-harmonic:v1 .

run-px4 model="2":
    docker run -it --gpus all \
        --rm \
        --privileged --network host \
        -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
        -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
        -v $HOME/.Xauthority:/root/.Xauthority \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        --name px4-gazebo-harmonic-tmp \
        px4-gazebo-harmonic:v1 \
        /bin/bash -c "source ~/.bashrc && runsim.sh {{model}}"

enter-px4:
    docker exec -it px4-gazebo-harmonic-tmp /bin/bash

clean-px4:
    docker rm -f px4-gazebo-harmonic-tmp

df-docker:
    docker system df

# attach
alias a := enter-ros2
enter-ros2:
    docker exec -it ros2-vtol bash

# Docker Compose commands
up:
    docker compose up -d

down:
    docker compose down

dc-restart:
    docker compose restart

develop-ros2:
    docker run --rm \
        --privileged --net=host \
        -itd \
        -w /home/ros/ros2_ws \
        -e DISPLAY=$DISPLAY -e QT_X11_NO_MITSHM=1 \
        -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
        -v $HOME/.Xauthority:/home/ros/.Xauthority \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v {{justfile_directory()}}/src:/home/ros/ros2_ws/src \
        -v {{justfile_directory()}}/scripts:/home/ros/ros2_ws/scripts \
        -v {{justfile_directory()}}/justfile:/home/ros/ros2_ws/justfile \
        --name ros2 \
        ros2
