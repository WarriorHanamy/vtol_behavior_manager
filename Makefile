# =============================================================================
# Build PX4
# =============================================================================

.PHONY: docker-build-px4

docker-build-px4:
	@git $(GIT_SAFE_FLAGS) submodule update --init --recursive $(PX4_SUBMODULE_PATH)
	@echo ">>> Tagging px4-deps as px4_deps..."
	@docker tag px4-deps:jammy-harmonic px4_deps:latest
	@echo ">>> Building px4-gazebo image..."
	@docker build $(DOCKER_BUILD_FLAGS) \
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

# Jetson variables
DOCKER := docker
PLATFORM := linux/arm64
IMAGE_PREFIX ?= vtol
IMAGE_SUFFIX ?= jetson
ROS2_IMAGE := $(IMAGE_PREFIX)/ros2-$(IMAGE_SUFFIX):latest
PX4_IMAGE := $(IMAGE_PREFIX)/px4-gazebo-$(IMAGE_SUFFIX):v1
QGC_IMAGE := $(IMAGE_PREFIX)/qgc5-$(IMAGE_SUFFIX):latest

# Deployment configuration (fixed convention)
HOST_IP := 192.168.55.100
DEVICE_IP := 192.168.55.1
DEVICE_USER := nv
IMAGE_DIR := /tmp/vtol-images
REMOTE_DIR := /tmp/vtol-images
SSH_KEY := ~/.ssh/id_ed25519
SSH_OPTS := $(if $(wildcard $(SSH_KEY)),-i $(SSH_KEY),)

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
# Simulation Environment (systemd user service)
# =============================================================================

# New systemd-based sim session
.PHONY: sim
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

# docker-shell removed; use docker-run-ros2-jetson-shell for Jetson or docker compose exec for host

# =============================================================================
# Jetson Targets (ARM64 cross-compilation)
# =============================================================================

.PHONY: docker-build-ros2-jetson
docker-build-ros2-jetson:
	$(DOCKER) run --rm --privileged tonistiigi/binfmt --install arm64 || true
	$(DOCKER) buildx build \
		--platform $(PLATFORM) \
		-f dockerfiles/ros2.dockerfile \
		-t $(ROS2_IMAGE) \
		--load \
		.

.PHONY: docker-build-px4-jetson
docker-build-px4-jetson:
	$(DOCKER) run --rm --privileged tonistiigi/binfmt --install arm64 || true
	$(DOCKER) buildx build \
		--platform $(PLATFORM) \
		-f dockerfiles/px4-gazebo.dockerfile \
		-t $(PX4_IMAGE) \
		--load \
		.

.PHONY: docker-build-qgc5-jetson
docker-build-qgc5-jetson:
	$(DOCKER) run --rm --privileged tonistiigi/binfmt --install arm64 || true
	$(DOCKER) buildx build \
		--platform $(PLATFORM) \
		-f dockerfiles/qgc5.dockerfile \
		-t $(QGC_IMAGE) \
		--load \
		.

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

.PHONY: docker-run-px4-jetson
docker-run-px4-jetson:
	$(DOCKER) run --rm \
		--platform $(PLATFORM) \
		--net=host \
		--ipc=host \
		--privileged \
		-e ROS_DOMAIN_ID=30 \
		-e DISPLAY=$(DISPLAY) \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(HOME)/.Xauthority:/tmp/.docker.xauth:ro \
		$(PX4_IMAGE) \
		bash -c "set +u; source /opt/ros/humble/setup.bash 2>/dev/null || true; set -u; exec bash"

.PHONY: docker-run-px4-jetson-shell
docker-run-px4-jetson-shell:
	$(DOCKER) run --rm -it \
		--platform $(PLATFORM) \
		--net=host \
		--ipc=host \
		--privileged \
		-e ROS_DOMAIN_ID=30 \
		-e DISPLAY=$(DISPLAY) \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(HOME)/.Xauthority:/tmp/.docker.xauth:ro \
		$(PX4_IMAGE) \
		bash -c "set +u; source /opt/ros/humble/setup.bash 2>/dev/null || true; set -u; exec bash"

.PHONY: docker-run-qgc5-jetson
docker-run-qgc5-jetson:
	$(DOCKER) run --rm \
		--platform $(PLATFORM) \
		--net=host \
		--ipc=host \
		--privileged \
		-e DISPLAY=$(DISPLAY) \
		-e QT_X11_NO_MITSHM=1 \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(HOME)/.Xauthority:/home/qgc/.Xauthority \
		$(QGC_IMAGE) \
		qgc

.PHONY: docker-run-qgc5-jetson-shell
docker-run-qgc5-jetson-shell:
	$(DOCKER) run --rm -it \
		--platform $(PLATFORM) \
		--net=host \
		--ipc=host \
		--privileged \
		-e DISPLAY=$(DISPLAY) \
		-e QT_X11_NO_MITSHM=1 \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(HOME)/.Xauthority:/home/qgc/.Xauthority \
		$(QGC_IMAGE) \
		bash

# Neural Services Management (group-based)
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

.PHONY: neural-infer
neural-infer: sync-policies
	@echo ">>> Running neural_infer in ros2 container..."
	@CONTAINER=$$(docker ps --filter "name=ros2" --format "{{.Names}}" | head -n 1); \
	if [ -z "$$CONTAINER" ]; then \
		echo "Error: ros2 container not running. Use 'make sim' first."; \
		exit 1; \
	fi; \
	echo ">>> Syncing src to container..."; \
	docker cp src/. "$$CONTAINER":/home/ros/ros2_ws/src/; \
	docker exec -i -u ros "$$CONTAINER" /bin/bash -lc "source /opt/ros/humble/setup.bash && cd /home/ros/ros2_ws && source install/setup.bash && PYTHONPATH=/home/ros/ros2_ws/src:\$$PYTHONPATH python3 -m neural_manager.neural_inference.neural_infer"

# =============================================================================
# Deployment targets (fixed convention: host=192.168.55.100, device=192.168.55.1)
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

.PHONY: export-images
export-images: check-network
	@echo "[INFO] Exporting Docker images..."
	@mkdir -p $(IMAGE_DIR)
	@for image in $(ROS2_IMAGE) $(PX4_IMAGE) $(QGC_IMAGE); do \
		filename=$$(echo "$$image" | tr '/:' '--').tar; \
		echo "[INFO] Exporting: $$image -> $$filename"; \
		$(DOCKER) save -o $(IMAGE_DIR)/$$filename $$image || exit 1; \
	done
	@echo "[INFO] Generating checksums..."
	@cd $(IMAGE_DIR) && sha256sum *.tar > checksums.sha256
	@echo "[INFO] Generating manifest..."
	@cd $(IMAGE_DIR) && \
		echo "# VTOL Docker Image Manifest" > manifest.txt && \
		echo "# Generated: $$(date -Iseconds)" >> manifest.txt && \
		echo "# Host: $$(hostname)" >> manifest.txt && \
		echo "" >> manifest.txt && \
		for image in $(ROS2_IMAGE) $(PX4_IMAGE) $(QGC_IMAGE); do \
			filename=$$(echo "$$image" | tr '/:' '--').tar; \
			echo "$$filename $$image" >> manifest.txt; \
		done
	@echo "[INFO] Export completed: $(IMAGE_DIR)"

.PHONY: transfer-images
transfer-images: export-images
	@echo "[INFO] Transferring images to $(DEVICE_USER)@$(DEVICE_IP)..."
	@ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "mkdir -p $(REMOTE_DIR)"
	@for file in $(IMAGE_DIR)/*.tar $(IMAGE_DIR)/checksums.sha256 $(IMAGE_DIR)/manifest.txt; do \
		if [ -f "$$file" ]; then \
			filename=$$(basename "$$file"); \
			echo "[INFO] Transferring: $$filename"; \
			scp $(SSH_OPTS) -v "$$file" $(DEVICE_USER)@$(DEVICE_IP):$(REMOTE_DIR)/$$filename 2>&1 | \
				grep -E "^(.*%|Transferring|Bytes)" || true; \
		fi; \
	done
	@echo "[INFO] Transfer completed"

.PHONY: load-images
load-images: transfer-images
	@echo "[INFO] Loading images on device..."
	@ssh $(SSH_OPTS) $(DEVICE_USER)@$(DEVICE_IP) "cd $(REMOTE_DIR) && sha256sum -c checksums.sha256 && for f in *.tar; do docker load -i \$$f; done"

.PHONY: deploy-all
deploy-all: load-images
	@echo "[INFO] Deployment completed"
	@echo "[INFO] Images deployed to: $(DEVICE_IP):$(REMOTE_DIR)"
	@echo "[INFO] All images loaded on device"

.PHONY: deploy-skip-build
deploy-skip-build: check-network
	@echo "[INFO] Deploying without build..."
	@if [ ! -d "$(IMAGE_DIR)" ] || [ -z "$$(ls $(IMAGE_DIR)/*.tar 2>/dev/null)" ]; then \
		echo "[ERROR] No exported images found in $(IMAGE_DIR)"; \
		echo "[ERROR] Run 'make export-images' first"; \
		exit 1; \
	fi
	@$(MAKE) --no-print-directory load-images
	@echo "[INFO] Deployment completed (build skipped)"
	@echo "[INFO] Images deployed to: $(DEVICE_IP):$(REMOTE_DIR)"

# =============================================================================
# Help
# =============================================================================

.PHONY: list
list:
	@echo "Available targets:"
	@sed -n 's/^\([a-zA-Z_-][a-zA-Z0-9_-]*\):.*/  \1/p' $(MAKEFILE_LIST) | sort -u
