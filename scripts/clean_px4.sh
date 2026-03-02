#!/bin/bash
# Remove PX4 container

set -e

docker rm -f px4-gazebo-harmonic-tmp
