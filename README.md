# vtol_behavior_manager

`vtol_behavior_manager` contains the simulation-first development environment for the
upper-layer VTOL stack.

Its primary scope includes:

- state-machine development
- neural inference and related ROS 2 nodes
- PX4-facing application logic developed and validated in simulation first
- simulation orchestration such as `docker-compose.yml` and sim session services

## Role In The Full System

This directory should not be read as the complete real-world deployment by
itself.

Instead, `vtol_behavior_manager` provides the upper-layer behavior stack that is first
developed against a simulation backend. In real-world deployment, that backend
is replaced by the runtime providers under `../linker/` while keeping the
upper-layer logic conceptually consistent.

## Important Note

`docker-compose.yml` in this directory is for simulation-oriented setup only.
It is not the canonical description of the onboard real-world deployment layout.
