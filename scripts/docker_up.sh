#!/bin/bash
# Start Docker Compose services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "${PROJECT_ROOT}"
docker compose up -d
