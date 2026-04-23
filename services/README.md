# Simulation Session Service Architecture

This document describes the systemd-tmux hybrid architecture for managing the simulation-side VTOL session and neural services.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend                              │
│              (WebSocket/HTTP API)                        │
└─────────────────────┬───────────────────────────────────┘
                       │ systemctl --user start/stop
                       ▼
┌─────────────────────────────────────────────────────────┐
│              sim-session.service (Main Service)          │
│  - tmux session: vtol-sim                                │
│  - docker compose up (px4, qgc, bht)                    │
│  - docker compose down on stop                           │
└─────────────────────┬───────────────────────────────────┘
                       │
                       │ make neural-infer
                       ▼
              ┌─────────────────────┐
              │  tmux session:      │
              │  vtol-neural        │
              │  ┌───────────────┐  │
              │  │ Window 0:     │  │
              │  │ neural_gate   │◄─┘
              │  └───────────────┘
              │  ┌───────────────┐
              │  │ Window 1:     │
              │  │ neural_infer  │◄─ Python node
              │  └───────────────┘
              └─────────────────────┘
```

## Quick Start

```bash
# 1. Install sim-session service (one-time)
make install

# 2. Start simulation
make sim

# 3. Start neural nodes in tmux
make neural-infer

# 4. Attach to tmux session to view output
make neural-attach
#   - Switch windows: Ctrl+b then 0 or 1
#   - Detach: Ctrl+b d
#   - Quit: Exit in both windows or 'make neural-kill'

# 5. Stop neural nodes
make neural-kill

# 6. Stop simulation
make sim-kill
```

## Make Targets

### Simulation Control
```bash
make sim              # Start docker compose (px4, qgc, bht)
make sim-kill         # Stop simulation
make sim-status       # Check sim-session.service status
make sim-attach       # Attach to simulation tmux (vtol-sim)
```

### Neural Services (tmux-based)
```bash
make neural-infer     # Start neural_gate + neural_infer in tmux
make neural-attach    # Attach to vtol-neural tmux session
make neural-kill      # Stop neural tmux session
```

### Support
```bash
make sync-policies    # Copy policies to bht container
```

## Systemd Services

### sim-session.service
- Manages docker compose lifecycle for simulation
- Creates tmux session `vtol-sim` for simulation tools
- Starts automatically on `make sim`
- Stops all containers on `make sim-kill`

### neural.target & test.target
- Legacy grouping targets (kept for compatibility)
- **Not used** by the new tmux workflow
- Can be ignored or removed in future

## Troubleshooting

### tmux session already exists
```bash
make neural-kill      # Kill existing session
make neural-infer     # Restart fresh
```

### Container not running
```bash
make sim              # Start simulation first
```

### Cannot attach to tmux
```bash
tmux ls               # List sessions
tmux kill-session -t vtol-neural   # Force cleanup
```

## Files

| File | Purpose |
|------|---------|
| `services/sim-session.service` | Main simulation session service |
| `services/neural.target` | Legacy target (unused) |
| `services/test.target` | Legacy target (unused) |
| `install-neural-services.sh` | Installation script (sim-session only) |
| `Makefile` | Make targets for control |

## Migration from Systemd

Previously, `neural_gate` and `neural_infer` ran as systemd user services.
These have been **replaced by the tmux workflow** (`make neural-infer`).

The `sim-session.service` remains unchanged for simulation management.
All other systemd units (neural_gate.service, neural_infer.service) are
no longer installed or used.
