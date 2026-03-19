.PHONY: up down qgc ros2-service ros2-kill ros2-ps px4-service px4-kill px4-ps colcon-rebuild neural-ctrl px4-sim sync-msg-submodule

# =============================================================================
# Quick Start
# =============================================================================

up: px4-service ros2-service qgc

down: ros2-kill px4-kill
	docker compose down

# =============================================================================
# QGroundControl
# =============================================================================

qgc:
	docker compose run --rm -d qgc

# =============================================================================
# ROS2 Workspace
# =============================================================================

ros2-service: ros2-kill
	docker compose run --rm -d ros2

ros2-kill: ros2-ps
	docker ps --filter "name=ros2" -q | xargs -r docker kill

ros2-ps:
	docker ps --filter "name=ros2" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

colcon-rebuild:
	docker compose run --rm ros2 colcon build

neural-ctrl:
	docker compose run --rm ros2 python3 src/neural_manager/neural_inference/neural_infer.py

# =============================================================================
# PX4 Gazebo Simulator
# =============================================================================

px4-service: px4-kill
	docker compose run --rm -d px4

px4-kill: px4-ps
	docker ps --filter "name=px4" -q | xargs -r docker kill

px4-ps:
	docker ps --filter "name=px4" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

px4-sim:
	docker compose exec px4 bash -c "cd /home/px4/PX4-Neupilot && HEADLESS=True make px4_sitl_default gz_x500"

# =============================================================================
# Submodule Sync
# =============================================================================

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
