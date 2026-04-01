# debug_px4

PX4 Zenoh debug subscriber with matplotlib visualization.

## Usage

```bash
cd deps/debug_px4

# Subscribe with print output
uv run debug-px4 -t neupilot/debug/acc_rates_control

# Subscribe with real-time plot
uv run debug-px4 -t neupilot/debug/acc_rates_control --plot

# Record standard MCAP with JSON messages
uv run debug-px4 -t neupilot/debug/acc_rates_control --mcap-output log.mcap

# Connect to specific zenoh router
uv run debug-px4 -t neupilot/debug/acc_rates_control -m client -l tcp/127.0.0.1:7447 --plot
```

## Adding new topics

1. Create `src/debug_px4/topics/<topic_name>.py` with dataclass and handler
2. Register in `src/debug_px4/topics/__init__.py`
