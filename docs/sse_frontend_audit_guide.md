# Frontend SSE Audit Guide: Log Streaming

This guide explains how frontend consumers can observe service errors through the SSE (Server-Sent Events) log stream provided by the log_streamer service.

## Overview

The log_streamer service provides HTTP endpoints that stream neural service logs via SSE. This allows frontend applications to receive real-time log updates without polling.

## Prerequisites

- log_streamer service must be running
- Backend services (neural_executor, neural_infer) must be installed
- Frontend must be able to make HTTP requests to log_streamer

## SSE Endpoints

### 1. Neural Executor Logs

**Endpoint:** `GET /logs/neural_executor`

**Description:** Streams logs from neural_executor service in real-time.

**Example Request:**
```bash
curl -N http://localhost:8000/logs/neural_executor \
  -H "Accept: text/event-stream"
```

**Example Response:**
```
data: {"MESSAGE": "Neural: Subscribed to /neural/control (VehicleThrustAccSetpoint)", "SERVICE": "neural_executor", "__REALTIME_TIMESTAMP": "1708627200000000", "PRIORITY": "6"}

data: {"MESSAGE": "State: Position", "SERVICE": "neural_executor", "__REALTIME_TIMESTAMP": "1708627201000000", "PRIORITY": "6"}
```

### 2. Neural Infer Logs

**Endpoint:** `GET /logs/neural_infer`

**Description:** Streams logs from neural_infer service in real-time.

**Example Request:**
```bash
curl -N http://localhost:8000/logs/neural_infer \
  -H "Accept: text/event-stream"
```

**Example Response:**
```
data: {"MESSAGE": "🔍 Checking neural_executor readiness...", "SERVICE": "neural_infer", "__REALTIME_TIMESTAMP": "1708627300000000", "PRIORITY": "6"}

data: {"MESSAGE": "✅ neural_executor is ready. Starting neural_infer...", "SERVICE": "neural_infer", "__REALTIME_TIMESTAMP": "1708627310000000", "PRIORITY": "6"}
```

### 3. Merged Logs

**Endpoint:** `GET /logs/merged`

**Description:** Streams logs from both neural_executor and neural_infer services, with a `service` field to identify the source.

**Example Request:**
```bash
curl -N http://localhost:8000/logs/merged \
  -H "Accept: text/event-stream"
```

**Example Response:**
```
data: {"MESSAGE": "Neural: Subscribed to /neural/control", "SERVICE": "neural_executor", "service": "neural_executor", "PRIORITY": "6"}

data: {"MESSAGE": "✅ neural_executor is ready", "SERVICE": "neural_infer", "service": "neural_infer", "PRIORITY": "6"}
```

### 4. Service Status

**Endpoint:** `GET /status`

**Description:** Returns JSON with current status of both services.

**Example Request:**
```bash
curl http://localhost:8000/status
```

**Example Response:**
```json
{
  "neural_executor": "active",
  "neural_infer": "active"
}
```

## SSE Data Format

All SSE events follow this format:

```
data: {json_payload}\n\n
```

The JSON payload includes the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `MESSAGE` | string | The log message |
| `SERVICE` | string | The systemd service name |
| `service` | string (optional) | Service identifier for merged logs |
| `__REALTIME_TIMESTAMP` | string | Unix timestamp in microseconds |
| `PRIORITY` | number | Log priority (0=emerg, 1=alert, 2=crit, 3=err, 4=warning, 5=notice, 6=info, 7=debug) |

## Frontend Integration Examples

### JavaScript (EventSource)

```javascript
// Connect to merged logs endpoint
const eventSource = new EventSource('http://localhost:8000/logs/merged');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Display log message
  console.log(`[${data.service}] ${data.MESSAGE}`);

  // Check for errors
  if (data.PRIORITY <= 3) {  // emerg, alert, crit, err
    displayError(data.MESSAGE, data.service);
  }

  // Update readiness status
  if (data.MESSAGE.includes('Subscribed to /neural/control')) {
    updateExecutorStatus('ready');
  }
};

eventSource.onerror = (error) => {
  console.error('SSE connection error:', error);
  // Attempt reconnection after delay
  setTimeout(() => {
    eventSource.close();
    // Re-create EventSource
  }, 5000);
};

// Close connection when done
eventSource.close();
```

### React Hook

```javascript
import { useState, useEffect } from 'react';

function useNeuralLogs() {
  const [logs, setLogs] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  useEffect(() => {
    const eventSource = new EventSource('http://localhost:8000/logs/merged');

    eventSource.onopen = () => {
      setConnectionStatus('connected');
    };

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs(prev => [...prev, data].slice(-1000)); // Keep last 1000 logs
    };

    eventSource.onerror = () => {
      setConnectionStatus('error');
    };

    return () => {
      eventSource.close();
    };
  }, []);

  return { logs, connectionStatus };
}

// Usage in component
function LogViewer() {
  const { logs, connectionStatus } = useNeuralLogs();
  const errorLogs = logs.filter(log => log.PRIORITY <= 3);

  return (
    <div>
      <div>Status: {connectionStatus}</div>
      <div>Error Count: {errorLogs.length}</div>
      <ul>
        {logs.map((log, index) => (
          <li key={index} className={log.PRIORITY <= 3 ? 'error' : 'info'}>
            [{log.service}] {log.MESSAGE}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### Python (sseclient)

```python
import sseclient
import requests

def stream_neural_logs():
    """Stream neural service logs via SSE."""
    response = requests.get(
        'http://localhost:8000/logs/merged',
        stream=True,
        headers={'Accept': 'text/event-stream'}
    )

    client = sseclient.SSEClient(response)

    for event in client.events():
        data = json.loads(event.data)

        # Process log entry
        print(f"[{data['SERVICE']}] {data['MESSAGE']}")

        # Check for errors
        if data['PRIORITY'] <= 3:
            handle_error(data['MESSAGE'], data['SERVICE'])

        # Check readiness
        if 'Subscribed to /neural/control' in data['MESSAGE']:
            print('neural_executor is ready!')

if __name__ == '__main__':
    stream_neural_logs()
```

## Error Handling

### Detecting Errors

Error logs can be identified by the `PRIORITY` field:

- **PRIORITY 0-3**: Critical errors (emerg, alert, crit, err)
- **PRIORITY 4**: Warnings
- **PRIORITY 5-7**: Normal messages (notice, info, debug)

```javascript
if (data.PRIORITY <= 3) {
  // Handle error
  displayAlert(data.MESSAGE, data.SERVICE);
} else if (data.PRIORITY === 4) {
  // Handle warning
  displayWarning(data.MESSAGE, data.SERVICE);
}
```

### Connection Errors

The SSE connection may fail or be interrupted. Implement reconnection logic:

```javascript
let eventSource = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

function connect() {
  eventSource = new EventSource('http://localhost:8000/logs/merged');

  eventSource.onerror = () => {
    if (reconnectAttempts < maxReconnectAttempts) {
      reconnectAttempts++;
      setTimeout(connect, 1000 * reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
    }
  };

  eventSource.onopen = () => {
    reconnectAttempts = 0; // Reset on successful connection
  };
}

connect();
```

## Service Status Monitoring

Before streaming logs, check service status:

```javascript
async function checkServiceStatus() {
  const response = await fetch('http://localhost:8000/status');
  const status = await response.json();

  console.log('neural_executor:', status.neural_executor);
  console.log('neural_infer:', status.neural_infer);

  return status;
}

// Poll status periodically
setInterval(checkServiceStatus, 30000); // Every 30 seconds
```

## Best Practices

1. **Reconnection**: Always implement reconnection logic for SSE connections
2. **Rate Limiting**: Don't process every single log message if volume is high
3. **Buffer Management**: Limit the number of stored log entries (e.g., keep last 1000)
4. **Error Aggregation**: Aggregate similar errors to avoid alert fatigue
5. **Timestamp Handling**: Convert Unix timestamps to human-readable format
6. **Filtering**: Implement client-side filtering for relevance

```javascript
// Example: Filter by service
const executorLogs = logs.filter(log => log.SERVICE === 'neural_executor');

// Example: Filter by time range
const recentLogs = logs.filter(log => {
  const timestamp = parseInt(log.__REALTIME_TIMESTAMP) / 1000; // Convert to seconds
  const cutoff = Date.now() / 1000 - 3600; // Last hour
  return timestamp > cutoff;
});

// Example: Filter errors only
const errors = logs.filter(log => log.PRIORITY <= 3);
```

## Troubleshooting

### No logs streaming

1. Check if log_streamer is running:
   ```bash
   systemctl --user status log_streamer
   ```

2. Check if log_streamer endpoint is accessible:
   ```bash
   curl http://localhost:8000/health
   ```

3. Check backend service status:
   ```bash
   systemctl --user status neural_executor neural_infer
   ```

### Connection dropped frequently

1. Check system logs for errors:
   ```bash
   journalctl --user -u log_streamer -f
   ```

2. Verify log_streamer has journal access
3. Check network connectivity

### Missing log messages

1. Verify backend services are producing logs:
   ```bash
   journalctl --user -u neural_executor -f
   ```

2. Check log_streamer logs for errors:
   ```bash
   journalctl --user -u log_streamer -f
   ```

## Quick Reference

```bash
# Test SSE endpoints
curl -N http://localhost:8000/logs/merged -H "Accept: text/event-stream"

# Check service status
curl http://localhost:8000/status

# Health check
curl http://localhost:8000/health
```

## Additional Resources

- log_streamer source: `log_streamer/main.py`
- Test examples: `test/scenario/test_stream_*.py`
- Systemd units: `services/*.service`
