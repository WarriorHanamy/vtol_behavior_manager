#!/bin/bash
# Build PX4 Gazebo Docker image

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Proxy configuration
PROXY_HOST="${PROXY_HOST:-internal_proxy}"
PROXY_PORT="${PROXY_PORT:-7890}"

DOCKER_BUILDKIT=1 docker build \
    --add-host=internal_proxy:172.17.208.1 \
    --build-arg http_proxy=http://${PROXY_HOST}:${PROXY_PORT} \
    --build-arg https_proxy=http://${PROXY_HOST}:${PROXY_PORT} \
    --build-arg HTTP_PROXY=http://${PROXY_HOST}:${PROXY_PORT} \
    --build-arg HTTPS_PROXY=http://${PROXY_HOST}:${PROXY_PORT} \
    --build-arg no_proxy=localhost,127.0.0.1 \
    --build-arg NO_PROXY=localhost,127.0.0.1 \
    -f "${PROJECT_ROOT}/docker/px4-gazebo.dockerfile" \
    -t px4-gazebo-harmonic:v1 \
    "${PROJECT_ROOT}"
