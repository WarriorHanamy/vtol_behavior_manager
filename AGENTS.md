# vtol_behavior_manager Development Guide

This document provides guidelines for developing within the `vtol_behavior_manager` repository.

## Development Environment

The development OS is Arch Linux. ROS cannot be used natively and must run in Docker.

## Build Information

When you need compilation logs to decide next steps:

- Use `make docker-offload-build` to build in Docker
- Logs are written to `build/compile.log`
- Do NOT attempt native `colcon build` on Arch Linux

## LINT & FORMAT
### python codes

Run
```bash
uv run ruff check --fix .
```

Never use Optional for type hinting.

## Running Python

```bash
uv run --no-sync python script.py
```

## Math Conventions

- This repo quaternion convention is `(w, x, y, z)`.
- `px4_msg` quaternion convention is `(w, x, y, z)`.
- A 3D vector expressed in a world frame should use frame-first naming, for example `ned_position` and `ned_velocity`.
- A frame-specific quaternion must encode both frames in its name using `source_quat_target`, for example `ned_quat_frd` and `enu_quat_flu`.
- Do not use bare names like `quat` for frame-specific quaternions, except when accessing external-library fields such as `msg.q`.
- Any quaternion returned by a `get_*` method must be canonicalized so `quat[0] >= 0`.

## Testing

All tests run inside the bht container. No host-side mocking.

```bash
make test    # copy test/ + src/ to container, source setup.bash, pytest -v
```

Pipeline: copy → source setup.bash → `python3 -m pytest test/ -v`

Requires `make sim` (or manually start bht container) first.
