"""Main FastAPI application for log streaming."""

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Log Streamer", version="0.1.0")

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
  app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def stream_journalctl(service_name: str) -> AsyncGenerator[str, None]:
  """Stream journalctl output as SSE events."""
  # Use journalctl --user to read user service logs
  cmd = [
    "journalctl",
    "--user",
    "-u",
    service_name,
    "-f",  # Follow logs
    "-n",
    "10",  # Show last 10 entries
    "--output=json",
  ]

  process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

  try:
    while True:
      line = await process.stdout.readline()
      if not line:
        break

      try:
        log_entry = json.loads(line.decode())
        # Send as SSE event
        yield f"data: {json.dumps(log_entry)}\n\n"
      except json.JSONDecodeError:
        # Skip malformed lines
        continue
  finally:
    if process.returncode is None:
      process.kill()
      await process.wait()


async def get_service_status(service_name: str) -> str:
  """Get service status using systemctl."""
  cmd = ["systemctl", "--user", "show", service_name, "--property=ActiveState"]

  process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

  stdout, _ = await process.communicate()
  output = stdout.decode().strip() if stdout else ""

  # Parse output: "ActiveState=active"
  if "=" in output:
    state = output.split("=", 1)[1]
  else:
    state = "inactive"

  return state


@app.get("/health")
def health():
  """Health check endpoint."""
  return {"status": "ok"}


@app.get("/")
def index():
  """Serve dashboard UI."""
  index_path = STATIC_DIR / "index.html"
  if index_path.exists():
    return FileResponse(index_path)
  return {"error": "Dashboard not found"}


@app.get("/logs/neural_executor")
async def logs_neural_executor():
  """Stream neural_executor logs via SSE."""
  return StreamingResponse(stream_journalctl("neural_executor"), media_type="text/event-stream")


@app.get("/logs/neural_infer")
async def logs_neural_infer():
  """Stream neural_infer logs via SSE."""
  return StreamingResponse(stream_journalctl("neural_infer"), media_type="text/event-stream")


@app.get("/logs/merged")
async def merged_logs():
  """Stream merged logs from both services via SSE."""

  async def merged_stream() -> AsyncGenerator[str, None]:
    """Merge logs from both services."""
    # Stream both services
    services = ["neural_executor", "neural_infer"]

    # Create async generators for each service
    async def stream_service(service: str) -> AsyncGenerator[str, None]:
      """Stream logs for a single service."""
      cmd = ["journalctl", "--user", "-u", service, "-f", "-n", "10", "--output=json"]

      process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
      )

      try:
        while True:
          line = await process.stdout.readline()
          if not line:
            break

          try:
            log_entry = json.loads(line.decode())
            # Add service identifier
            log_entry["service"] = service
            yield f"data: {json.dumps(log_entry)}\n\n"
          except json.JSONDecodeError:
            continue
      finally:
        if process.returncode is None:
          process.kill()
          await process.wait()

    # Create tasks for both services
    tasks = [stream_service(service) for service in services]

    # Yield from all services sequentially
    for task in tasks:
      async for line in task:
        yield line

  return StreamingResponse(merged_stream(), media_type="text/event-stream")


@app.get("/status")
async def status():
  """Get status of neural services."""
  services = ["neural_executor", "neural_infer"]
  result = {}

  for service in services:
    state = await get_service_status(service)
    result[service] = {"status": state}

  return result
