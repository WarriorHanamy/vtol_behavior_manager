# Development Environment

The development OS is Arch Linux. ROS cannot be used natively and must run in Docker.

# LINT & FORMAT
## python codes

Run
```bash
uv run ruff check --fix .
```

Never use Optional for type hinting.
