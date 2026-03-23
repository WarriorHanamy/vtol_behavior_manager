.PHONY: build

TMP_SRC := /tmp/vtol-interface-src

build:
	@echo ">>> Copying src to $(TMP_SRC)..."
	@rm -rf $(TMP_SRC)
	@cp -r src $(TMP_SRC)
	docker compose run --rm \
		-v $(TMP_SRC):/home/ros/ros2_ws/src \
		ros2 bash -c "cp -r src/px4_msgs/msg/versioned/* src/px4_msgs/msg/ && source /opt/ros/humble/setup.bash && colcon build"

# =============================================================================
# Submodule Sync
# =============================================================================

.PHONY: sync-msg-submodule

REF_NEUPILOT_REMOTE ?= https://github.com/WarriorHanamy/PX4-Neupilot.git
MSG_SUBMODULE_PATH := src/px4_msgs/msg

sync-msg-submodule:
	@echo ">>> Syncing msg submodule to ref-neupilot..."
	@if ! git remote | grep -q '^ref-neupilot$$'; then \
		echo ">>> Adding ref-neupilot remote..."; \
		git remote add ref-neupilot $(REF_NEUPILOT_REMOTE); \
	fi
	@echo ">>> Fetching ref-neupilot..."
	git fetch ref-neupilot
	@MSG_COMMIT=$$(git ls-tree ref-neupilot/main msg | awk '{print $$3}'); \
	MSG_URL=$$(git show ref-neupilot/main:.gitmodules | grep -A3 '\[submodule "msg"\]' | grep 'url' | sed 's/.*= *//'); \
	echo ">>> Target commit: $$MSG_COMMIT"; \
	echo ">>> Target URL: $$MSG_URL"; \
	echo ">>> Updating submodule remote URL..."; \
	cd $(MSG_SUBMODULE_PATH) && git remote set-url origin $$MSG_URL && git fetch origin && git checkout $$MSG_COMMIT; \
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
	@echo ">>> Starting simulation session via systemd..."
	@systemctl --user start sim-session.service
	@echo ">>> Waiting for ros2 container to be ready..."
	@for i in $$(seq 1 30); do \
		if docker ps --filter "name=ros2" --format "{{.Names}}" | grep -q .; then \
			echo ">>> ros2 container ready"; \
			echo ">>> Starting neural services (Group A)..."; \
			systemctl --user start neural.target; \
			echo ">>> Done. Use 'make sim-attach' to attach to tmux."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Warning: ros2 container not ready after 30s"; \
	echo "Start neural services manually with: make neural"

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

.PHONY: install neural-start neural-stop neural-status logs logs-web neural test

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
