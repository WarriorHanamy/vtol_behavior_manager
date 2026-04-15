# =============================================================================
# VTOL Behavior Manager - Docker Build & Simulation
# =============================================================================
#
# Dual-Workflow Design:
# 1. Simulation (amd64): docker-compose based, full stack (ros2 + px4 + qgc)
# 2. Deployment Build (arm64): Two-stage Jetson image build following linker pattern
#
# Key targets:
#   make sim                    - Start simulation environment (docker-compose)
#   make sim-kill               - Stop simulation
#   make docker-offload-ros2BuildTask - Build in simulation container
#   make docker-build-ros2-jetson - Build Jetson deployment image (two-stage)
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
IMAGE_DIR := /tmp/vtol-images
REMOTE_DIR := /tmp/vtol-images
SSH_KEY := ~/.ssh/id_ed25519
SSH_OPTS := $(if $(wildcard $(SSH_KEY)),-i $(SSH_KEY),)

# Prep image and archive for two-stage build
ROS2_PREP_IMAGE := $(IMAGE_PREFIX)/bht-prep-$(IMAGE_SUFFIX):latest
ROS2_PREP_ARCHIVE := $(IMAGE_DIR)/bht-prep-$(IMAGE_SUFFIX).tar
ROS2_REMOTE_BUILD_DIR := $(REMOTE_DIR)/bht-native

# =============================================================================
# Shipping macro (copied from linker)
# =============================================================================
# ship-to-device: copy prep archive and full dockerfiles/ to device
# $(1) = prep archive path (local)
# $(2) = remote build directory
define ship-to-device
  @ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "rm -rf $(2) && mkdir -p $(2)/dockerfiles"
  @scp $(SSH_OPTS) $(1) $(DEVICE_USER)@$(DEVICE_IP):$(REMOTE_DIR)/
  @scp $(SSH_OPTS) -r dockerfiles/. $(DEVICE_USER)@$(DEVICE_IP):$(2)/dockerfiles/
endef

# =============================================================================
# Simulation Environment (systemd user service, amd64)
# =============================================================================

.PHONY: sim

sim:
	@echo ">>> Granting X11 access to docker..."
	@xhost +local:docker 2>/dev/null || true
	@echo ">>> Passing DISPLAY to systemd..."
	@systemctl --user import-environment DISPLAY
	@echo ">>> Starting simulation session via systemd..."
	@systemctl --user start sim-session.service
	@echo ">>> Waiting for bht container to be ready..."
	@for i in $$(seq 1 30); do \
		if docker ps --filter "name=bht" --format "{{.Names}}" | grep -q .; then \
			echo ">>> bht container ready"; \
			echo ">>> Done. Use 'make sim-attach' to attach to tmux."; \
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

.PHONY: sim-attach

sim-attach:
	@tmux attach -t vtol-sim 2>/dev/null || echo "Session not running. Use 'make sim' first."

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
		 colcon build --packages-select neural_executor 2>&1" | tee build/compile.log
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
	@./install-neural-services.sh

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
	@echo ">>> Running neural_infer in bht container..."
	@CONTAINER=$$(docker ps --filter "name=bht" --format "{{.Names}}" | head -n 1); \
	if [ -z "$$CONTAINER" ]; then \
		echo "Error: bht container not running. Use 'make sim' first."; \
		exit 1; \
	fi; \
	echo ">>> Syncing src to container..."; \
	docker cp src/. "$$CONTAINER":/home/ros/ros2_ws/src/; \
	docker exec -i -u ros "$$CONTAINER" /bin/bash -lc "source /opt/ros/humble/setup.bash && cd /home/ros/ros2_ws && source install/setup.bash && PYTHONPATH=/home/ros/ros2_ws/src:\$$PYTHONPATH python3 -m neural_manager.neural_inference.neural_infer"

# =============================================================================
# Deployment Build (Jetson, arm64) - Two-stage pattern from linker
# =============================================================================

.PHONY: docker-build-ros2-jetson

docker-build-ros2-jetson: check-network
	@echo "[1/4] Building BHT prep image locally for $(PLATFORM)..."
	@mkdir -p $(IMAGE_DIR)
	$(DOCKER) run --rm --privileged tonistiigi/binfmt --install arm64 || true
	$(DOCKER) buildx build \
		--platform $(PLATFORM) \
		-f dockerfiles/bht.prep.Dockerfile \
		--target prep \
		-t $(ROS2_PREP_IMAGE) \
		--output type=docker,dest=$(ROS2_PREP_ARCHIVE) \
		.
	@echo "[2/4] Shipping prep image and native Dockerfile to $(DEVICE_USER)@$(DEVICE_IP)..."
	$(call ship-to-device,$(ROS2_PREP_ARCHIVE),$(ROS2_REMOTE_BUILD_DIR))
	@echo "[3/4] Loading prep image on Jetson..."
	@ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "docker load -i $(REMOTE_DIR)/$(notdir $(ROS2_PREP_ARCHIVE))"
	@echo "[4/4] Building final BHT image natively on Jetson..."
	@ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "docker build --network=host -f $(ROS2_REMOTE_BUILD_DIR)/dockerfiles/bht.native.Dockerfile --build-arg PREP_IMAGE=$(ROS2_PREP_IMAGE) -t $(ROS2_IMAGE) $(ROS2_REMOTE_BUILD_DIR)"

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
