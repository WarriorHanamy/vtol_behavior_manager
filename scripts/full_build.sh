#!/bin/bash
# Full build: config px4msgs + build workspace

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# First config px4msgs
"${SCRIPT_DIR}/config_px4msgs.sh"

# Then build
"${SCRIPT_DIR}/build.sh"
