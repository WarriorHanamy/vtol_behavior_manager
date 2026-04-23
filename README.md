# vtol_behavior_manager

Upper-layer VTOL behavior stack: neural inference, mode switching, and PX4 integration.

## Architecture

### Neural Gate State Machine

The `neural_gate` node implements a state machine based on PX4's `VehicleStatus.nav_state`:

```
                    ┌─────────────────────────────────────┐
                    │          PX4 VehicleStatus           │
                    │          nav_state                   │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         neural_gate tick()           │
                    │         (400Hz, 2.5ms)               │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼─────────┐  ┌──────▼──────┐  ┌─────────▼─────────┐
    │   NAV_STATE_POSCTL │  │ NAV_STATE_  │  │     default       │
    │                    │  │  OFFBOARD   │  │                   │
    └─────────┬─────────┘  └──────┬──────┘  └─────────┬─────────┘
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ 1. Publish       │  │ Do nothing      │  │ WARN_ONCE       │
    │    /neural/target│  │ (neural network │  │ "[GATE] current │
    │ 2. RC trigger    │  │  is in control) │  │  mode is %d,    │
    │    → offboard    │  │                 │  │  not supported" │
    └─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        POSCTL Mode                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  /fmu/out/vehicle_odometry                                          │
│       │                                                             │
│       ▼                                                             │
│  neural_gate.cpp ──► /neural/target ──► vtol_feature_provider.py    │
│  (position + offset)                        │                       │
│                                             ▼                       │
│                                    neural_infer.py                  │
│                                    (inference)                      │
│                                             │                       │
│                                             ▼                       │
│                              /fmu/in/vehicle_acc_rates_setpoint     │
│                              (direct, no gate)                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       OFFBOARD Mode                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  neural_gate: do nothing                                            │
│  neural_infer.py: continues publishing to                           │
│                   /fmu/in/vehicle_acc_rates_setpoint                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Mode Switching

**RC Trigger → Offboard:**

1. Pilot presses button or flips aux1 switch (edge detection)
2. `neural_gate` sends `VEHICLE_CMD_DO_SET_MODE` (offboard)
3. PX4 responds with `VehicleCommandAck`
4. `neural_gate` logs confirmation

**Stick Override → Position:**

1. Pilot moves sticks while in offboard mode
2. PX4 detects `sticks_moving` (via `COM_RC_OVERRIDE` parameter)
3. PX4 switches to POSCTL automatically
4. `neural_gate` state machine handles POSCTL mode

**Configuration:**

```bash
# Enable stick override for offboard mode
param set COM_RC_OVERRIDE 3  # bit 0 (auto) + bit 1 (offboard)
```

### Topics

| Topic | Publisher | Subscriber | Description |
|-------|-----------|------------|-------------|
| `/neural/target` | neural_gate | vtol_feature_provider | Target position (NED + offset) |
| `/fmu/in/vehicle_acc_rates_setpoint` | neural_infer | PX4 | Neural network control output |
| `/fmu/in/offboard_control_mode` | neural_gate | PX4 | Offboard heartbeat (10Hz) |
| `/fmu/in/vehicle_command` | neural_gate | PX4 | Mode switch command |
| `/fmu/out/vehicle_odometry` | PX4 | neural_gate, neural_infer | Vehicle state |
| `/fmu/out/vehicle_status` | PX4 | neural_gate | Navigation state |
| `/fmu/out/vehicle_command_ack` | PX4 | neural_gate | Command acknowledgment |
| `/fmu/out/manual_control_setpoint` | PX4 | neural_gate | RC input |

### Parameters

**neural_gate:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `button_mask` | 1024 | Bitmask for button trigger |
| `aux1_on_threshold` | 0.6 | Aux1 value to activate trigger |
| `aux1_off_threshold` | 0.4 | Aux1 value to deactivate trigger |
| `target_offset` | [0,0,0] | Position offset [x,y,z] in meters |

**PX4:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| `COM_RC_OVERRIDE` | 3 | Enable stick override for auto + offboard |

## Development

### Simulation (amd64)

```bash
make sim                              # Start simulation (ros2 + px4-gazebo + qgc)
make sim-kill                         # Stop simulation
make docker-offload-ros2BuildTask     # Build neural_gate in container
make neural-infer                     # Run inference in simulation
```

### Deployment (arm64, Jetson)

```bash
make docker-build-ros2-jetson         # Build ARM64 image
make docker-run-ros2-jetson           # Test image locally
```

### Build Verification

```bash
make docker-offload-ros2BuildTask 2>&1 | tee build/compile.log
# Expected: "1 package finished" with no errors
```

## File Structure

```
vtol_behavior_manager/
├── src/
│   ├── neural_manager/
│   │   ├── neural_gate/
│   │   │   ├── src/neural_gate.cpp          # State machine mode switch
│   │   │   ├── launch/neural_gate.launch.py
│   │   │   └── CMakeLists.txt
│   │   └── neural_inference/
│   │       ├── neural_infer.py              # Neural network inference
│   │       ├── control/
│   │       │   ├── action_post_processor.py
│   │       │   └── control_publisher.py
│   │       ├── features/
│   │       │   └── vtol_feature_provider.py
│   │       └── config/
│   │           └── pos_ctrl_config.yaml
│   └── px4_msgs/                            # PX4 message definitions
├── docker-compose.yml                       # Simulation orchestration
└── Makefile                                 # Build and simulation targets
```
