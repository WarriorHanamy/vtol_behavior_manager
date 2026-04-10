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

## Development Workflow

### Simulation (amd64)

The simulation environment runs the full VTOL stack locally using docker-compose:

```bash
make sim              # Start simulation (ros2 + px4-gazebo + qgc)
make sim-kill         # Stop simulation
make sim-attach       # Attach to tmux session
make sim-status       # Check simulation status
make docker-offload-ros2BuildTask  # Build neural_executor in container
make neural-infer      # Run inference in simulation
```

This workflow is for rapid development and testing on a workstation.

### Deployment Build (arm64, Jetson)

To build the ROS2 image for Jetson deployment:

```bash
make docker-build-ros2-jetson   # Two-stage ARM64 build (prep + native)
make docker-run-ros2-jetson      # Test the built image locally
make docker-run-ros2-jetson-shell  # Open shell in Jetson image
```

This uses a two-stage Docker build pattern:
1. **Prep stage**: Cross-compile dependencies on host (ARM64) → tarball
2. **Native stage**: Final colcon build on Jetson device

The built image is tagged as `vtol/ros2-jetson:latest`.

**Note**: Image deployment (transfer to device) is handled by the `linker` repository's workflow.
This repository focuses on building and simulation only.

### Naming Conventions

- **Simulation images**: Local development names
  - `ros2-vtol:latest`
  - `px4-gazebo-harmonic-vtol:v1`
  - `qgc5-vtol:latest`

- **Deployment image**: Production naming following linker convention
  - `vtol/ros2-jetson:latest`

## Makefile Targets

Key targets categorized by workflow:

| Category | Targets |
|----------|---------|
| Simulation | `sim`, `sim-kill`, `sim-status`, `sim-attach` |
| Simulation Build | `docker-offload-ros2BuildTask`, `sync-msg-submodule` |
| Simulation Services | `install`, `sync-policies`, `neural-infer` |
| Deployment Build | `docker-build-ros2-jetson`, `docker-run-ros2-jetson`, `docker-run-ros2-jetson-shell` |
| Utilities | `check-network`, `list` |

For the full list, run `make list`.
