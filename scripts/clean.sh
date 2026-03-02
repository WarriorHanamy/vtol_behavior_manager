#!/bin/bash
# Clean build artifacts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Remove build, log, and install directories
[ -d "${PROJECT_ROOT}/build" ] && rm -rf "${PROJECT_ROOT}/build"
[ -d "${PROJECT_ROOT}/log" ] && rm -rf "${PROJECT_ROOT}/log"
[ -d "${PROJECT_ROOT}/install" ] && rm -rf "${PROJECT_ROOT}/install"

echo "Cleaned build artifacts"
