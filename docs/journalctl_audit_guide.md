# Operator Audit Guide: Journalctl Commands

This guide provides operators with journalctl commands for monitoring and auditing neural services logs.

## Prerequisites

- neural_executor and neural_infer services must be installed and running
- User must have access to journalctl (standard Linux system)

## Live Log Tailing

### Monitor all neural services in real-time

```bash
# Tail both neural_executor and neural_infer logs
journalctl --user -u neural_executor.service -u neural_infer.service -f

# Tail with timestamps
journalctl --user -u neural_executor.service -u neural_infer.service -f --since "1 minute ago"

# Tail with priority filtering (show only warnings and errors)
journalctl --user -u neural_executor.service -u neural_infer.service -f -p warning..err
```

### Monitor individual services

```bash
# Monitor only neural_executor
journalctl --user -u neural_executor.service -f

# Monitor only neural_infer
journalctl --user -u neural_infer.service -f
```

## Error Filtering

### Filter for errors only

```bash
# Show all errors from neural services
journalctl --user -u neural_executor.service -u neural_infer.service -p err

# Show errors with context (5 lines before and after)
journalctl --user -u neural_executor.service -u neural_infer.service -p err -n 0 -b

# Show only error messages (grep pattern)
journalctl --user -u neural_executor.service -u neural_infer.service | grep -i "error"
```

### Filter for warnings and errors

```bash
# Show warnings and errors
journalctl --user -u neural_executor.service -u neural_infer.service -p warning..err

# Show warnings and errors for last hour
journalctl --user -u neural_executor.service -u neural_infer.service -p warning..err --since "1 hour ago"
```

## Historical Review

### Review logs from a specific time range

```bash
# Logs from the last 30 minutes
journalctl --user -u neural_executor.service -u neural_infer.service --since "30 minutes ago"

# Logs from a specific date
journalctl --user -u neural_executor.service -u neural_infer.service --since "2026-03-22 10:00:00" --until "2026-03-22 11:00:00"

# Logs from the current boot
journalctl --user -u neural_executor.service -u neural_infer.service -b
```

### Review last N entries

```bash
# Last 100 lines
journalctl --user -u neural_executor.service -u neural_infer.service -n 100

# Last 1000 lines with pager disabled
journalctl --user -u neural_executor.service -u neural_infer.service -n 1000 --no-pager
```

### Search for specific patterns

```bash
# Search for "ready" messages
journalctl --user -u neural_executor.service | grep -i "ready"

# Search for subscription messages
journalctl --user -u neural_executor.service | grep "Subscribed"

# Search for neural control messages
journalctl --user -u neural_executor.service -u neural_infer.service | grep -i "neural"
```

## Service Status and Health

### Check service status

```bash
# Check neural_executor status
systemctl --user status neural_executor.service

# Check neural_infer status
systemctl --user status neural_infer.service

# Check both services
systemctl --user status neural_executor.service neural_infer.service
```

### Verify neural_executor readiness

```bash
# Check if neural_executor has subscribed to /neural/control
journalctl --user -u neural_executor.service | grep "Subscribed to /neural/control"

# Check recent readiness logs
journalctl --user -u neural_executor.service --since "5 minutes ago" | grep -i "ready\|subscribed"
```

## Advanced Queries

### Export logs to file

```bash
# Export last hour of logs to JSON
journalctl --user -u neural_executor.service -u neural_infer.service --since "1 hour ago" --output=json > neural_logs.json

# Export to plain text
journalctl --user -u neural_executor.service -u neural_infer.service --since "1 hour ago" > neural_logs.txt
```

### Monitor CPU and resource usage

```bash
# Monitor with process stats
journalctl --user -u neural_executor.service -u neural_infer.service -f | grep -i "cpu\|memory\|resource"

# Show system resource impact
journalctl --user -u neural_executor.service -u neural_infer.service --since "10 minutes ago" | grep -i "warning\|error"
```

## Troubleshooting Common Issues

### neural_executor not starting

```bash
# Check for startup errors
journalctl --user -u neural_executor.service -n 50 | grep -i "error\|failed"

# Verify ros2 container is accessible
journalctl --user -u neural_executor.service | grep -i "container\|docker"

# Check for subscription issues
journalctl --user -u neural_executor.service | grep "Subscribed"
```

### neural_infer timeout waiting for executor

```bash
# Check neural_executor readiness
journalctl --user -u neural_executor.service | grep "Subscribed to /neural/control"

# Check neural_infer startup logs
journalctl --user -u neural_infer.service | grep -i "checking\|ready\|timeout"

# Verify both services are active
systemctl --user status neural_executor.service neural_infer.service
```

### Communication issues between services

```bash
# Check neural_executor for topic subscription
journalctl --user -u neural_executor.service | grep -i "/neural/control"

# Check neural_infer for topic publication
journalctl --user -u neural_infer.service | grep -i "publish\|topic"

# Look for connection errors
journalctl --user -u neural_executor.service -u neural_infer.service | grep -i "error\|failed\|timeout"
```

## Quick Reference

```bash
# Quick health check
journalctl --user -u neural_executor.service -u neural_infer.service -n 20

# Monitor in real-time
journalctl --user -u neural_executor.service -u neural_infer.service -f

# Check for errors
journalctl --user -u neural_executor.service -u neural_infer.service -p err

# Verify readiness
journalctl --user -u neural_executor.service | grep "Subscribed to /neural/control"
```
