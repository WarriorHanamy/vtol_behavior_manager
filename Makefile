.PHONY: up down qgc ros2-service ros2-kill ros2-ps px4-service px4-kill px4-ps build-ros2 neural-ctrl

# Quick start: launch all services
up: px4-service ros2-service qgc

# Stop all services
down: ros2-kill px4-kill
	docker compose down

# QGroundControl
qgc:
	docker compose run --rm -d qgc

# ROS2 Workspace
ros2-service: ros2-kill
	docker compose run --rm -d ros2

ros2-kill: ros2-ps
	docker ps --filter "name=ros2" -q | xargs -r docker kill

ros2-ps:
	docker ps --filter "name=ros2" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

# Build ROS2 workspace (run once after code changes)
build-ros2:
	docker compose run --rm ros2 bash -c "source /opt/ros/humble/setup.bash && colcon build"

# Start neural control node
neural-ctrl:
	docker compose run --rm ros2 bash -c "source /opt/ros/humble/setup.bash && source install/setup.bash && python3 src/neural_manager/neural_inference/neural_infer.py"

# PX4 Gazebo Simulator
px4-service: px4-kill
	docker compose run --rm -d px4

px4-kill: px4-ps
	docker ps --filter "name=px4" -q | xargs -r docker kill

px4-ps:
	docker ps --filter "name=px4" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

# Start PX4 VTOL simulation (inside px4 container)
px4-sim:
	docker compose exec px4 bash -c "cd /root/PX4-Neupilot && make px4_sitl gz_x500_vtol"
