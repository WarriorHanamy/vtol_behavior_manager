# Test Executor Service

Test Executor Service runs the test neural executor node inside the BHT container with a joystick readiness gate.

## Prerequisites

### Joystick/RC Requirement
The test executor service requires a joystick or RC controller to be **connected and active** before starting. The service will fail fast if the joystick is not ready.

**Joystick readiness check:**
- The service checks if `_manual_control_input->buttons()` is available
- This means the joystick must be connected and PX4 must be publishing valid manual control setpoints
- The readiness probe waits up to 5 seconds for the joystick to become ready

**Before starting the service, ensure:**
1. Joystick/RC is connected to your system
2. PX4 (or simulator) is running and publishing manual control setpoints
3. Joystick is in manual mode with buttons active

## Installation

Install the test executor service as a user systemd unit:

```bash
./install-neural-services.sh
```

This creates a symlink from `services/test_executor.service` to `~/.config/systemd/user/test_executor.service`.

## Starting the Service

### Prerequisite: Start BHT Container
The test executor service runs inside the BHT Docker Compose container. Start the container first:

```bash
# Option 1: Using make (recommended)
make sim

# Option 2: Using docker compose directly
docker compose up -d bht
```

### Start Test Executor Service

```bash
# Enable the service (auto-start on login)
systemctl --user enable test_executor.service

# Start the service immediately
systemctl --user start test_executor.service

# Or do both in one command
systemctl --user enable --now test_executor.service
```

### Verify Service Status

```bash
# Check if service is running
systemctl --user status test_executor.service

# Check all neural services
systemctl --user status neural_executor.service neural_infer.service test_executor.service
```

## Service Logs and Auditing

### View Live Logs

```bash
# Follow logs in real-time
journalctl --user -u test_executor.service -f

# View logs for all neural services
journalctl --user -u neural_executor.service -u neural_infer.service -u test_executor.service -f
```

### Audit Historical Logs

```bash
# View last 100 lines of logs
journalctl --user -u test_executor.service -n 100

# View logs since service started
journalctl --user -u test_executor.service --since today

# View logs with timestamps and priority
journalctl --user -u test_executor.service -o verbose

# Export logs to a file
journalctl --user -u test_executor.service > test_executor_logs.txt
```

### Common Audit Queries

```bash
# Search for joystick readiness errors
journalctl --user -u test_executor.service | grep -i "joystick"

# Search for service start events
journalctl --user -u test_executor.service | grep -i "Starting test"

# Search for errors
journalctl --user -u test_executor.service -p err

# Search for container discovery events
journalctl --user -u test_executor.service | grep -i "container"
```

## Troubleshooting

### Service Fails to Start

**Symptom:** Service exits with "Joystick not ready" error

**Solution:**
1. Verify joystick/RC is connected
2. Verify PX4 or simulator is running
3. Verify PX4 is publishing manual control setpoints:
   ```bash
    # Inside bht container
    docker exec -it <bht-container-name> bash
   source /opt/ros/humble/setup.bash
   source install/setup.bash
   ros2 topic echo /fmu/in/manual_control_setpoint --once
   ```
4. If using a simulator, ensure the manual control input is enabled

**Symptom:** Service exits with "bht container not found" error

**Solution:**
1. Verify the bht container is running:
   ```bash
   docker ps --filter "name=bht"
   ```
2. Start the container:
   ```bash
   make sim
   # or
   docker compose up -d bht
   ```

### Service Restarts Repeatedly

**Symptom:** Service enters restart loop (Restart=on-failure with 5s interval)

**Solution:**
1. Check logs for error messages:
   ```bash
   journalctl --user -u test_executor.service -n 50
   ```
2. Verify joystick is still connected and active
3. Check if BHT container is healthy
4. Verify the test_neural_executor launch file exists:
   ```bash
   ls -la src/neural_manager/neural_executor/launch/test_neural_executor.launch.py
   ```

### Readiness Probe Timeout

**Symptom:** Service fails with "Joystick readiness timeout after 5.0s"

**Solution:**
1. Check if PX4 is publishing manual control setpoints
2. Verify the joystick buttons are being pressed/active
3. Current readiness signal requires non-zero buttons value
4. Increase timeout if needed (edit the service file ExecStartPre section)

## Stopping the Service

```bash
# Stop the service
systemctl --user stop test_executor.service

# Disable the service (prevent auto-start on login)
systemctl --user disable test_executor.service

# Stop and disable in one command
systemctl --user disable --now test_executor.service
```

## Service Details

**Service File:** `services/test_executor.service`

**Launch File:** `src/neural_manager/neural_executor/launch/test_neural_executor.launch.py`

**Readiness Probe:** `src/neural_manager/neural_executor/scripts/joystick_readiness_probe.py`

**Current Readiness Signal:** `_manual_control_input->buttons()` availability (non-zero value)

**Container Discovery:** Dynamic (finds running container with "bht" in name)

**Restart Policy:** on-failure with 5 second interval

## Advanced: Modifying Readiness Signal

The readiness signal is isolated in the probe script to allow future changes without modifying the service flow.

To change the readiness signal:
1. Edit `src/neural_manager/neural_executor/scripts/joystick_readiness_probe.py`
2. Modify the `manual_control_callback()` method to check a different condition
3. No changes needed to the service file

Example: Change to check sticks moving instead of buttons:
```python
def manual_control_callback(self, msg: ManualControlSetpoint):
    if msg.valid:
        # Changed from buttons() to sticks_moving()
        if msg.sticks_moving:
            self.ready = True
```

## Integration with Make Targets

The test executor service integrates with existing Make targets:

```bash
# Install services (includes test_executor)
make install

# Start bht container
make sim

# Start neural services (includes test_executor if enabled)
make neural-start

# Stop neural services
make neural-stop

# Check service status
make neural-status

# View logs
make logs
```

Note: `make neural-start` starts neural_executor and neural_infer by default. To start test_executor, use systemctl directly as shown above.
