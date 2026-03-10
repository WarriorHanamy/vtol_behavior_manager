.PHONY: ros2-service ros2-kill ros2-ps px4-service px4-kill px4-ps

ros2-service: ros2-kill
	docker compose run --rm -d ros2

ros2-kill: ros2-ps
	docker ps --filter "name=ros2" -q | xargs -r docker kill

ros2-ps:
	docker ps --filter "name=ros2" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"

px4-service: px4-kill
	docker compose run --rm -d px4

px4-kill: px4-ps
	docker ps --filter "name=px4" -q | xargs -r docker kill

px4-ps:
	docker ps --filter "name=px4" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"
