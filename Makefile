.PHONY: ros2-service ros2-kill ros2-ps

ros2-service: ros2-kill
	docker compose run --rm -d ros2

ros2-kill: ros2-ps
	docker ps --filter "name=ros2" -q | xargs -r docker kill

ros2-ps:
	docker ps --filter "name=ros2" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"
