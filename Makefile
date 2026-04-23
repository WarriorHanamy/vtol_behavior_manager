# =============================================================================
# VTOL Behavior Manager - Docker Build & Simulation
# =============================================================================
#
# Dual-Workflow Design:
# 1. Simulation (amd64): docker-compose based, full stack (ros2 + px4 + qgc)
# 2. Deployment Build (arm64): Single-stage Jetson image build
#
# Key targets:
#   make sim                    - Start simulation environment (docker-compose)
#   make sim-kill               - Stop simulation
#   make docker-offload-ros2BuildTask - Build in simulation container
#   make docker-build-ros2-jetson - Build Jetson deployment image (single-stage)
#   make docker-run-ros2-jetson   - Test deployment image locally
#
# Deployment (image transfer) is handled by the 'linker' repository.
# =============================================================================

# =============================================================================
# Build Offload (for AI decision-making in simulation)
# =============================================================================

VTOL_OFFLOAD_CONTAINER ?= vtol-build-offload
VTOL_OFFLOAD_IMAGE ?= bht-vtol:latest
PX4_SUBMODULE_PATH := deps/PX4-Neupilot
GIT_SAFE_FLAGS := -c safe.directory=$(CURDIR) -c safe.directory=$(abspath $(PX4_SUBMODULE_PATH))

# =============================================================================
# Jetson variables (for deployment build and testing)
# =============================================================================

DOCKER := docker
PLATFORM := linux/arm64
IMAGE_PREFIX ?= vtol
IMAGE_SUFFIX ?= jetson

# Deployment image naming (following linker convention)
ROS2_IMAGE := $(IMAGE_PREFIX)/bht-$(IMAGE_SUFFIX):latest

# =============================================================================
# Deployment configuration (copied from linker - fixed convention)
# =============================================================================

HOST_IP := 192.168.55.100
DEVICE_IP := 192.168.55.1
DEVICE_USER := nv

REMOTE_DIR := /tmp/vtol-images
SSH_KEY := ~/.ssh/id_ed25519
SSH_OPTS := $(if $(wildcard $(SSH_KEY)),-i $(SSH_KEY),)

# Remote build directory for native build
ROS2_REMOTE_BUILD_DIR := $(REMOTE_DIR)/bht-native

# =============================================================================
# Shipping macro (copied from linker)
# =============================================================================
# ship-context-to-device: copy build context to device
# $(1) = remote build directory
define ship-context-to-device
  @ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "rm -rf $(1) && mkdir -p $(1)"
  @rsync -avz --exclude='.git' --exclude='build' --exclude='.venv' --exclude='__pycache__' \
    -e "ssh $(SSH_OPTS)" . $(DEVICE_USER)@$(DEVICE_IP):$(1)/
endef

# =============================================================================
# Simulation Environment (systemd user service, amd64)
# =============================================================================

.PHONY: sim

sim:
	@echo ">>> Granting X11 access to docker..."
	@xhost +local:docker 2>/dev/null || true
	@echo ">>> Passing GUI session env to systemd..."
	@systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS XAUTHORITY
	@echo ">>> Starting simulation session via systemd..."
	@systemctl --user start sim-session.service
	@echo ">>> Waiting for bht container to be ready..."
	@for i in $$(seq 1 30); do \
		if docker ps --filter "name=bht" --format "{{.Names}}" | grep -q .; then \
			echo ">>> bht container ready"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Warning: bht container not ready after 30s"

.PHONY: sim-kill

sim-kill:
	@echo ">>> Stopping simulation session..."
	@systemctl --user stop sim-session.service 2>/dev/null || true
	@tmux kill-session -t vtol-sim 2>/dev/null || echo "Session not found or already dead"

.PHONY: sim-status

sim-status:
	@systemctl --user status sim-session.service --no-pager


# =============================================================================
# Build targets (simulation offload, amd64)
# =============================================================================

.PHONY: docker-offload-build-image

docker-offload-build-image:
	@echo ">>> Building offload image $(VTOL_OFFLOAD_IMAGE)..."
	$(DOCKER) build -t $(VTOL_OFFLOAD_IMAGE) -f dockerfiles/bht.dockerfile .

.PHONY: docker-offload-ros2BuildTask

docker-offload-ros2BuildTask:
	@docker rm -f $(VTOL_OFFLOAD_CONTAINER) > /dev/null 2>&1 || true
	@mkdir -p build
	@docker run --rm -d --name $(VTOL_OFFLOAD_CONTAINER) $(VTOL_OFFLOAD_IMAGE) sleep infinity
	@docker cp src/neural_manager $(VTOL_OFFLOAD_CONTAINER):/home/ros/ros2_ws/src/
	@docker exec $(VTOL_OFFLOAD_CONTAINER) bash -lc \
		"source /opt/ros/humble/setup.bash && \
		 source /home/ros/ros2_ws/install/setup.bash && \
		 colcon build --packages-select neural_gate 2>&1" | tee build/compile.log
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
# Neural Services Management (simulation)
# =============================================================================

.PHONY: install

install:
	@echo ">>> Installing neural services..."
	@if [ "$(shell id -u)" -eq 0 ]; then \
		echo "Error: This target should NOT be run as root"; \
		echo "User services must be installed for the current user"; \
		exit 1; \
	fi
	@./services/install-neural-services.sh

POLICIES_SRC ?= /home/rec/server/policies

.PHONY: sync-policies

sync-policies:
	@echo ">>> Copying policies to bht container..."
	@CONTAINER=$$(docker ps --filter "name=bht" --format "{{.Names}}" | head -n 1); \
	if [ -z "$$CONTAINER" ]; then \
		echo "Error: bht container not running. Use 'make sim' first."; \
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

.PHONY: neural-infer

neural-infer: sync-policies
	@echo ">>> Starting neural services in tmux session 'vtol-neural'..."
	@CONTAINER=$$(docker ps --filter "name=bht" --format "{{.Names}}" | head -n 1); \
	if [ -z "$$CONTAINER" ]; then \
		echo "Error: bht container not running. Use 'make sim' first."; \
		exit 1; \
	fi; \
	echo ">>> Syncing src to container..."; \
	docker cp src/. "$$CONTAINER":/home/ros/ros2_ws/src/; \
	SESSION="vtol-neural"; \
	tmux has-session -t $$SESSION 2>/dev/null && tmux kill-session -t $$SESSION; \
	tmux new-session -d -s $$SESSION; \
	tmux new-window -t $$SESSION -n gate "docker exec -i -u ros $$CONTAINER /bin/bash -lc 'source /opt/ros/humble/setup.bash && cd /home/ros/ros2_ws && source install/setup.bash && ros2 launch neural_gate neural_gate.launch.py'"; \
	tmux new-window -t $$SESSION -n infer "docker exec -i -u ros $$CONTAINER /bin/bash -lc 'source /opt/ros/humble/setup.bash && cd /home/ros/ros2_ws && source install/setup.bash && PYTHONPATH=/home/ros/ros2_ws/src:\$$PYTHONPATH python3 -m neural_manager.neural_inference.neural_infer'"; \
	echo ">>> Tmux session '$$SESSION' created with 2 windows:"; \
	echo "    - gate:   Neural Gate launch"; \
	echo "    - infer:  Neural Inference"; \
	echo ">>> Attaching... (detach with Ctrl+b then d)"; \
	sleep 1; \
	exec tmux attach -t $$SESSION

.PHONY: neural-attach

neural-attach:
	@tmux attach -t vtol-neural 2>/dev/null || echo "Session not running. Use 'make neural-infer' first."

# =============================================================================
# Shipping targets (copied from linker)
# =============================================================================

.PHONY: ship-context

ship-context:
	@echo ">>> Copying build context to Jetson (excluding deps/)..."
	@ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "rm -rf $(ROS2_REMOTE_BUILD_DIR) && mkdir -p $(ROS2_REMOTE_BUILD_DIR)"
	@rsync -avz --exclude='.git' --exclude='build' --exclude='.venv' --exclude='__pycache__' --exclude='deps/' \
		-e "ssh $(SSH_OPTS)" . $(DEVICE_USER)@$(DEVICE_IP):$(ROS2_REMOTE_BUILD_DIR)/

# =============================================================================
# Deployment Build (Jetson, arm64) - Native single-stage build
# =============================================================================

.PHONY: docker-build-ros2-jetson

docker-build-ros2-jetson: check-network ship-context
	@echo "[1/2] Building BHT image natively on Jetson..."
	@ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "cd $(ROS2_REMOTE_BUILD_DIR) && docker build --network=host -f dockerfiles/bht.native.Dockerfile -t $(ROS2_IMAGE) ."
	@echo "[2/2] Build complete. Image: $(ROS2_IMAGE)"

.PHONY: docker-run-ros2-jetson

docker-run-ros2-jetson:
	$(DOCKER) run --rm \
		--platform $(PLATFORM) \
		--net=host \
		--ipc=host \
		--privileged \
		-e ROS_DOMAIN_ID=30 \
		-e DISPLAY=$(DISPLAY) \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(HOME)/.Xauthority:/home/ros/.Xauthority \
		$(ROS2_IMAGE) \
		bash -c "set +u; source /opt/ros/humble/setup.bash && source /home/ros/ros2_ws/install/setup.bash; set -u; exec bash"

.PHONY: docker-run-ros2-jetson-shell

docker-run-ros2-jetson-shell:
	$(DOCKER) run --rm -it \
		--platform $(PLATFORM) \
		--net=host \
		--ipc=host \
		--privileged \
		-e ROS_DOMAIN_ID=30 \
		-e DISPLAY=$(DISPLAY) \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(HOME)/.Xauthority:/home/ros/.Xauthority \
		$(ROS2_IMAGE) \
		bash -c "set +u; source /opt/ros/humble/setup.bash && source /home/ros/ros2_ws/install/setup.bash; set -u; exec bash"

# =============================================================================
# Network check (required for Jetson deployment build)
# =============================================================================

.PHONY: check-network

check-network:
	@echo "[INFO] Checking network convention..."
	@echo "[INFO] Host IP: $(HOST_IP)"
	@echo "[INFO] Device IP: $(DEVICE_IP)"
	@if ! ip addr show | grep -q "inet $(HOST_IP)/"; then \
		echo "[ERROR] Host does not have IP $(HOST_IP)"; \
		echo "[ERROR] This is a deployment convention - host must have $(HOST_IP)"; \
		exit 1; \
	fi
	@echo "[INFO] Host IP $(HOST_IP) found"
	@if ! ping -c 2 -W 3 $(DEVICE_IP) >/dev/null 2>&1; then \
		echo "[ERROR] Cannot reach device at $(DEVICE_IP)"; \
		echo "[ERROR] Check physical connection and device power"; \
		exit 1; \
	fi
	@echo "[INFO] Device $(DEVICE_IP) reachable"
	@echo "[INFO] Network convention check passed"

# =============================================================================
# Help
# =============================================================================

.PHONY: list

list:
	@echo "Available targets:"
	@sed -n 's/^\([a-zA-Z_-][a-zA-Z0-9_-]*\):.*/  \1/p' $(MAKEFILE_LIST) | sort -u
