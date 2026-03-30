.PHONY: list docker-offload-build docker-px4-build docker-ros2-build

# =============================================================================
# Build ROS2 Image (layered by change frequency)
# =============================================================================

docker-ros2-build:
	@echo ">>> Building ros2-vtol image (layered: px4_msgs -> px4-ros2 -> neural_manager)..."
	@docker build -f dockerfiles/ros2.dockerfile -t ros2-vtol:latest .

# =============================================================================
# Build PX4
# =============================================================================

docker-px4-build:
	@git $(GIT_SAFE_FLAGS) submodule update --init --recursive $(PX4_SUBMODULE_PATH)
	@echo ">>> Tagging px4-deps as px4_deps..."
	@docker tag px4-deps:jammy-harmonic px4_deps:latest
	@echo ">>> Building px4-gazebo image..."
	@docker build $(DOCKER_BUILD_FLAGS) \
		--build-arg PX4_GIT_URL="$(PX4_GIT_URL)" \
		--build-arg PX4_GIT_REF="$(PX4_GIT_REF)" \
		--build-arg PX4_GIT_COMMIT="$(PX4_GIT_COMMIT)" \
		--build-arg PX4_GIT_TAG="$(PX4_GIT_TAG)" \
		-f dockerfiles/px4-gazebo.dockerfile \
		-t px4-gazebo-harmonic-vtol:v1 .

# =============================================================================
# Build Offload (for AI decision-making)
# =============================================================================

VTOL_OFFLOAD_CONTAINER ?= vtol-build-offload
VTOL_OFFLOAD_IMAGE ?= ros2-vtol:latest
PX4_SUBMODULE_PATH := deps/PX4-Neupilot
GIT_SAFE_FLAGS := -c safe.directory=$(CURDIR) -c safe.directory=$(abspath $(PX4_SUBMODULE_PATH))
DOCKER_BUILD_FLAGS ?=
PX4_GIT_URL ?= $(shell git $(GIT_SAFE_FLAGS) -C "$(PX4_SUBMODULE_PATH)" remote get-url origin 2>/dev/null)
PX4_GIT_REF ?= $(shell git $(GIT_SAFE_FLAGS) -C "$(PX4_SUBMODULE_PATH)" symbolic-ref --quiet --short HEAD 2>/dev/null || printf 'main')
PX4_GIT_COMMIT ?= $(shell git $(GIT_SAFE_FLAGS) -C "$(PX4_SUBMODULE_PATH)" rev-parse HEAD 2>/dev/null)
PX4_GIT_TAG ?= $(shell git $(GIT_SAFE_FLAGS) -C "$(PX4_SUBMODULE_PATH)" describe --exclude ext/* --always --tags --dirty 2>/dev/null)

docker-offload-build:
	@docker rm -f $(VTOL_OFFLOAD_CONTAINER) > /dev/null 2>&1 || true
	@mkdir -p build
	@docker run --rm -d --name $(VTOL_OFFLOAD_CONTAINER) $(VTOL_OFFLOAD_IMAGE) sleep infinity
	@docker cp src/neural_manager $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker exec $(VTOL_OFFLOAD_CONTAINER) bash -lc \
		"source /opt/ros/humble/setup.bash && \
		 source /home/ros/ros2_ws/install/setup.bash && \
		 colcon build --packages-select neural_executor 2>&1" | tee build/compile.log
	@docker stop $(VTOL_OFFLOAD_CONTAINER) > /dev/null
	@echo ">>> Build log: build/compile.log"

.PHONY: docker-build-px4-msgs docker-build-px4-ros2 docker-build-neural docker-build-all

docker-build-px4-msgs:
	@docker rm -f $(VTOL_OFFLOAD_CONTAINER) > /dev/null 2>&1 || true
	@mkdir -p build
	@docker run --rm -d --name $(VTOL_OFFLOAD_CONTAINER) $(VTOL_OFFLOAD_IMAGE) sleep infinity
	@docker cp src/px4_msgs $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker exec $(VTOL_OFFLOAD_CONTAINER) bash -lc \
		"cp -r /home/ros/ros2_ws/src/px4_msgs/msg/versioned/* /home/ros/ros2_ws/src/px4_msgs/msg/ && \
		 source /opt/ros/humble/setup.bash && \
		 colcon build --packages-select px4_msgs 2>&1" | tee build/compile.log
	@docker stop $(VTOL_OFFLOAD_CONTAINER) > /dev/null
	@echo ">>> Build log: build/compile.log"

docker-build-px4-ros2:
	@docker rm -f $(VTOL_OFFLOAD_CONTAINER) > /dev/null 2>&1 || true
	@mkdir -p build
	@docker run --rm -d --name $(VTOL_OFFLOAD_CONTAINER) $(VTOL_OFFLOAD_IMAGE) sleep infinity
	@docker cp src/px4_msgs $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker cp src/px4-ros2-interface-lib $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker exec $(VTOL_OFFLOAD_CONTAINER) bash -lc \
		"cp -r /home/ros/ros2_ws/src/px4_msgs/msg/versioned/* /home/ros/ros2_ws/src/px4_msgs/msg/ && \
		 source /opt/ros/humble/setup.bash && \
		 colcon build --packages-select px4_msgs px4_ros2_cpp 2>&1" | tee build/compile.log
	@docker stop $(VTOL_OFFLOAD_CONTAINER) > /dev/null
	@echo ">>> Build log: build/compile.log"

docker-build-neural:
	@docker rm -f $(VTOL_OFFLOAD_CONTAINER) > /dev/null 2>&1 || true
	@mkdir -p build
	@docker run --rm -d --name $(VTOL_OFFLOAD_CONTAINER) $(VTOL_OFFLOAD_IMAGE) sleep infinity
	@docker cp src/neural_manager $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker exec $(VTOL_OFFLOAD_CONTAINER) bash -lc \
		"source /opt/ros/humble/setup.bash && \
		 source /home/ros/ros2_ws/install/setup.bash && \
		 colcon build --packages-select neural_executor 2>&1" | tee build/compile.log
	@docker stop $(VTOL_OFFLOAD_CONTAINER) > /dev/null
	@echo ">>> Build log: build/compile.log"

docker-build-all:
	@docker rm -f $(VTOL_OFFLOAD_CONTAINER) > /dev/null 2>&1 || true
	@mkdir -p build
	@docker run --rm -d --name $(VTOL_OFFLOAD_CONTAINER) $(VTOL_OFFLOAD_IMAGE) sleep infinity
	@docker cp src/. $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker exec $(VTOL_OFFLOAD_CONTAINER) bash -lc \
		"cp -r /home/ros/ros2_ws/src/px4_msgs/msg/versioned/* /home/ros/ros2_ws/src/px4_msgs/msg/ && \
		 source /opt/ros/humble/setup.bash && \
		 colcon build 2>&1" | tee build/compile.log
	@docker stop $(VTOL_OFFLOAD_CONTAINER) > /dev/null
	@echo ">>> Build log: build/compile.log"

# =============================================================================
# Submodule Sync
# =============================================================================

.PHONY: sync-msg-submodule

MSG_SUBMODULE_PATH := src/px4_msgs/msg

sync-msg-submodule:
	@echo ">>> Resolving msg submodule info..."; \
	if [ -d "$(PX4_SUBMODULE_PATH)" ]; then \
		MSG_COMMIT=$$(git $(GIT_SAFE_FLAGS) -C "$(PX4_SUBMODULE_PATH)" submodule status -- msg | sed 's/^[-+ ]//' | cut -d' ' -f1); \
		MSG_URL=$$(git $(GIT_SAFE_FLAGS) -C "$(PX4_SUBMODULE_PATH)" config -f .gitmodules submodule.msg.url); \
		echo ">>> Using local PX4 submodule metadata from $(PX4_SUBMODULE_PATH)"; \
	else \
		echo ">>> Local PX4 submodule not found, falling back to gh api..."; \
		MSG_COMMIT=$$(gh api repos/WarriorHanamy/PX4-Neupilot/git/trees/main --jq '.tree[] | select(.path=="msg") | .sha'); \
		MSG_URL=$$(gh api repos/WarriorHanamy/PX4-Neupilot/contents/.gitmodules --jq '.content' | base64 -d | grep -A3 '\[submodule "msg"\]' | grep 'url' | sed 's/.*= *//'); \
	fi; \
	echo ">>> Target commit: $$MSG_COMMIT"; \
	echo ">>> Target URL: $$MSG_URL"; \
	echo ">>> Direct checkout to commit..."; \
	cd $(MSG_SUBMODULE_PATH) && git remote set-url origin $$MSG_URL && git checkout $$MSG_COMMIT; \
	cd $(CURDIR) && git config -f .gitmodules submodule.$(MSG_SUBMODULE_PATH).url "$$MSG_URL"; \
	cd $(CURDIR) && git config submodule.$(MSG_SUBMODULE_PATH).url "$$MSG_URL"; \
	echo ">>> Submodule synced. Changes to commit:"; \
	git status --short $(MSG_SUBMODULE_PATH) .gitmodules

# =============================================================================
# Simulation Environment (systemd user service)
# =============================================================================

.PHONY: sim sim-kill sim-status sim-attach

# Legacy tmux-based sim (kept for reference)
sim-legacy: sim-kill
	@which tmux >/dev/null || { echo "Error: tmux not installed"; exit 1; }
	@echo ">>> Starting simulation session: $(TMUX_SESSION)"
	tmux new-session -d -s $(TMUX_SESSION) -n sim -x 200 -y 50
	tmux send-keys -t $(TMUX_SESSION) 'docker compose up -d px4 qgc && docker compose attach ros2; docker compose down; tmux kill-session -t $(TMUX_SESSION)' C-m
	tmux attach -t $(TMUX_SESSION)

# New systemd-based sim session
sim:
	@echo ">>> Granting X11 access to docker..."
	@xhost +local:docker 2>/dev/null || true
	@echo ">>> Passing DISPLAY to systemd..."
	@systemctl --user import-environment DISPLAY
	@echo ">>> Starting simulation session via systemd..."
	@systemctl --user start sim-session.service
	@echo ">>> Waiting for ros2 container to be ready..."
	@for i in $$(seq 1 30); do \
		if docker ps --filter "name=ros2" --format "{{.Names}}" | grep -q .; then \
			echo ">>> ros2 container ready"; \
			echo ">>> Done. Use 'make sim-attach' to attach to tmux."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Warning: ros2 container not ready after 30s"

sim-kill:
	@echo ">>> Stopping simulation session..."
	@systemctl --user stop sim-session.service 2>/dev/null || true
	@tmux kill-session -t vtol-sim 2>/dev/null || echo "Session not found or already dead"

sim-status:
	@systemctl --user status sim-session.service --no-pager

sim-attach:
	@tmux attach -t vtol-sim 2>/dev/null || echo "Session not running. Use 'make sim' first."

# =============================================================================
# Neural Services Management (group-based)
# =============================================================================

.PHONY: install neural-start neural-stop neural-status logs logs-web neural test neural-infer

install:
	@echo ">>> Installing neural services..."
	@if [ "$(shell id -u)" -eq 0 ]; then \
		echo "Error: This target should NOT be run as root"; \
		echo "User services must be installed for the current user"; \
		exit 1; \
	fi
	@./install-neural-services.sh

# Start Group A (neural_executor + neural_infer)
neural:
	@echo ">>> Switching to Neural Group A..."
	@systemctl --user isolate neural.target

# Start Group B (test_executor with joystick)
test:
	@echo ">>> Switching to Test Group B..."
	@systemctl --user isolate test.target

# Legacy targets (kept for compatibility)
neural-start:
	@echo ">>> Starting neural services (Group A)..."
	@systemctl --user isolate neural.target

neural-stop:
	@echo ">>> Stopping neural services..."
	@systemctl --user stop neural.target test.target 2>/dev/null || true

neural-status:
	@echo ">>> Checking service status..."
	@echo ""
	@echo "=== Sim Session ==="
	@systemctl --user status sim-session.service --no-pager || true
	@echo ""
	@echo "=== Neural Target (Group A) ==="
	@systemctl --user status neural.target --no-pager || true
	@echo ""
	@echo "=== Test Target (Group B) ==="
	@systemctl --user status test.target --no-pager || true

POLICIES_SRC ?= /home/rec/server/policies

sync-policies:
	@echo ">>> Copying policies to ros2 container..."
	@CONTAINER=$$(docker ps --filter "name=ros2" --format "{{.Names}}" | head -n 1); \
	if [ -z "$$CONTAINER" ]; then \
		echo "Error: ros2 container not running. Use 'make sim' first."; \
		exit 1; \
	fi; \
	if [ ! -d "$(POLICIES_SRC)" ]; then \
		echo "Error: Policies directory not found: $(POLICIES_SRC)"; \
		exit 1; \
	fi; \
	echo ">>> Source: $(POLICIES_SRC)"; \
	docker exec -u root "$$CONTAINER" mkdir -p /home/ros/policies && \
	if ! docker exec -u root "$$CONTAINER" chown ros:ros /home/ros/policies; then \
		echo ">>> Skipping chown for /home/ros/policies (read-only mount or restricted FS)"; \
	fi && \
	docker cp "$(POLICIES_SRC)/." "$$CONTAINER":/home/ros/policies/ && \
	echo ">>> Done. Policies copied to /home/ros/policies/"

neural-infer: sync-policies
	@echo ">>> Running neural_infer in ros2 container..."
	@CONTAINER=$$(docker ps --filter "name=ros2" --format "{{.Names}}" | head -n 1); \
	if [ -z "$$CONTAINER" ]; then \
		echo "Error: ros2 container not running. Use 'make sim' first."; \
		exit 1; \
	fi; \
	echo ">>> Syncing src to container..."; \
	docker cp src/. "$$CONTAINER":/home/ros/ros2_ws/src/; \
	docker exec -i -u ros "$$CONTAINER" /bin/bash -lc "source /opt/ros/humble/setup.bash && cd /home/ros/ros2_ws && source install/setup.bash && PYTHONPATH=/home/ros/ros2_ws/src:\$$PYTHONPATH python3 src/neural_manager/neural_inference/neural_infer.py"

logs:
	@echo ">>> Streaming all service logs (press Ctrl+C to exit)..."
	@journalctl --user -u sim-session.service -u neural_executor.service -u neural_infer.service -u test_executor.service -f

logs-web:
	@echo ">>> Log streamer web endpoints (requires log_streamer service to be running):"
	@echo ""
	@echo "Neural Executor logs:   http://localhost:8000/logs/neural_executor"
	@echo "Neural Inference logs:  http://localhost:8000/logs/neural_infer"
	@echo "Merged logs:            http://localhost:8000/logs/merged"
	@echo "Service status:         http://localhost:8000/status"
	@echo "Health check:           http://localhost:8000/health"
	@echo ""
	@echo "To start log_streamer service:"
	@echo "  docker compose up -d log_streamer"
	@echo ""
	@echo "To stop log_streamer service:"
	@echo "  docker compose stop log_streamer"

# =============================================================================
# Help
# =============================================================================

list:
	@echo "Available targets:"
	@sed -n 's/^\([a-zA-Z_-][a-zA-Z0-9_-]*\):.*/  \1/p' $(MAKEFILE_LIST) | sort -u
