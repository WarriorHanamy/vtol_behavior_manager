# Simulation Session Service Architecture

This document describes the systemd-based service architecture for managing VTOL simulation and neural services.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend                              │
│              (WebSocket/HTTP API)                        │
└─────────────────────┬───────────────────────────────────┘
                      │ systemctl --user start/stop sim-session
                      ▼
┌─────────────────────────────────────────────────────────┐
│              sim-session.service (Main Service)          │
│  - tmux session: vtol-sim                                │
│  - docker compose up (px4, qgc, ros2)                    │
│  - Auto-starts neural.target on success                  │
│  - docker compose down on stop                           │
└─────────────────────┬───────────────────────────────────┘
                      │ PartOf=sim-session.service
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│ neural.target │           │  test.target  │
│   (Group A)   │◄─Conflicts─►│   (Group B)  │
└───────┬───────┘           └───────┬───────┘
        │                           │
   ┌────┴────┐                      │
   ▼         ▼                      ▼
┌─────┐  ┌─────┐               ┌─────────┐
│exec.│  │infer│               │test_exec│
└─────┘  └─────┘               └─────────┘
```

## Service Groups

### Group A: Neural Services (Default)
- `neural_executor.service` - Neural executor node
- `neural_infer.service` - Neural inference node
- Started automatically when sim-session starts

### Group B: Test Executor
- `test_executor.service` - Test executor with joystick
- Requires joystick/RC to be connected
- Mutually exclusive with Group A

## Quick Start

```bash
# 1. Install services (one-time)
make install

# 2. Start simulation
make sim

# 3. Switch between groups
make neural    # Switch to Group A
make test      # Switch to Group B

# 4. Check status
make sim-status

# 5. Stop everything
make sim-kill
```

## Systemd Commands

### Session Control
```bash
# Start sim session
systemctl --user start sim-session.service

# Stop sim session (stops all services)
systemctl --user stop sim-session.service

# Check status
systemctl --user status sim-session.service

# View logs
journalctl --user -u sim-session.service -f
```

### Group Switching
```bash
# Switch to Group A (neural)
systemctl --user isolate neural.target

# Switch to Group B (test)
systemctl --user isolate test.target
```

### Individual Services
```bash
# Check neural services status
systemctl --user status neural_executor.service
systemctl --user status neural_infer.service

# Check test executor status
systemctl --user status test_executor.service

# View specific logs
journalctl --user -u neural_executor.service -f
journalctl --user -u test_executor.service -f
```

## Lifecycle Binding

When `sim-session.service` stops:
1. tmux session is killed
2. `docker compose down` is executed
3. All neural/test services stop (PartOf relationship)

When switching groups:
1. Current group services stop
2. New group services start
3. sim-session continues running

## Frontend Integration

The frontend can control the simulation via:

```bash
# Start sim
systemctl --user start sim-session.service

# Stop sim
systemctl --user stop sim-session.service

# Switch to neural group
systemctl --user isolate neural.target

# Switch to test group
systemctl --user isolate test.target

# Get status (JSON output available via systemctl --user show)
systemctl --user show sim-session.service --property=ActiveState,SubState
```

## Troubleshooting

### Service won't start
```bash
# Check if services are installed
ls -la ~/.config/systemd/user/

# Reload systemd
systemctl --user daemon-reload

# Check logs
journalctl --user -u sim-session.service -n 50
```

### tmux session not accessible
```bash
# List tmux sessions
tmux ls

# Attach to session
tmux attach -t vtol-sim

# Or use make target
make sim-attach
```

### Group switch fails
```bash
# Check if sim-session is running first
systemctl --user status sim-session.service

# Check target status
systemctl --user status neural.target
systemctl --user status test.target
```

## Files

| File | Purpose |
|------|---------|
| `services/sim-session.service` | Main simulation session service |
| `services/neural.target` | Group A target (neural services) |
| `services/test.target` | Group B target (test executor) |
| `services/neural_executor.service` | Neural executor service |
| `services/neural_infer.service` | Neural inference service |
| `services/test_executor.service` | Test executor service |
| `install-neural-services.sh` | Installation script |
| `Makefile` | Make targets for control |
