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
# Simulation Environment (tmux + docker compose)
# =============================================================================

.PHONY: sim sim-kill

TMUX_SESSION := vtol-sim

sim: sim-kill
	@which tmux >/dev/null || { echo "Error: tmux not installed"; exit 1; }
	@echo ">>> Starting simulation session: $(TMUX_SESSION)"
	tmux new-session -d -s $(TMUX_SESSION) -n sim -x 200 -y 50
	tmux send-keys -t $(TMUX_SESSION) 'docker compose up -d px4 qgc && docker compose attach ros2; docker compose down; tmux kill-session -t $(TMUX_SESSION)' C-m
	tmux attach -t $(TMUX_SESSION)

sim-kill:
	@echo ">>> Killing session: $(TMUX_SESSION)"
	tmux kill-session -t $(TMUX_SESSION) 2>/dev/null || echo "Session not found or already dead"
