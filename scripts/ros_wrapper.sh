#!/bin/bash
# Copyright (c) 2025, Differential Robotics
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
#
# ROS Environment Bootstrap Wrapper
#
# This script provides deterministic ROS environment loading for Python scripts.
# It implements the following contract:
# 1. Resolve ROS_DISTRO deterministically with default "humble" when empty or unset
# 2. Derive setup path exactly as /opt/ros/<distro>/setup.bash
# 3. Exit with non-zero status when setup file is missing

set -e

# Default ROS distribution
DEFAULT_ROS_DISTRO="humble"

# Resolve ROS_DISTRO environment variable
# If not set or empty, use default
ROS_DISTRO="${ROS_DISTRO:-$DEFAULT_ROS_DISTRO}"
if [ -z "$ROS_DISTRO" ]; then
    ROS_DISTRO="$DEFAULT_ROS_DISTRO"
fi

# Derive setup file path pattern: /opt/ros/<distro>/setup.bash
SETUP_FILE="/opt/ros/${ROS_DISTRO}/setup.bash"

# Validate setup file exists
if [ ! -f "$SETUP_FILE" ]; then
    echo "Error: ROS setup file not found: ${SETUP_FILE}" >&2
    echo "Please ensure ROS ${ROS_DISTRO} is installed or set ROS_DISTRO to a valid distribution" >&2
    exit 1
fi

# Source the ROS setup file
source "$SETUP_FILE"

# Export ROS_DISTRO for child processes
export ROS_DISTRO

# Execute the provided Python script
if [ $# -eq 0 ]; then
    echo "Error: No Python script provided" >&2
    echo "Usage: $0 <script.py> [args...]" >&2
    exit 1
fi

# Execute the script with provided arguments using python3
exec python3 "$@"
