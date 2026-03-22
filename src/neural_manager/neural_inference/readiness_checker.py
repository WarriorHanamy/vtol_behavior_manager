"""
Neural Executor Readiness Checker

This module provides functionality to check if neural_executor is ready by monitoring
its journalctl logs for the subscription to /neural/control topic.
"""

import json
import logging
import subprocess
from typing import Literal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The log message that indicates neural_executor is ready
READINESS_LOG_MESSAGE = "Neural: Subscribed to /neural/control (VehicleThrustAccSetpoint)"
READINESS_LOG_PATTERN = "Neural: Subscribed to /neural/control"

# Default timeout in seconds
DEFAULT_TIMEOUT = 30


def check_executor_ready() -> bool:
  """
  Check if neural_executor is ready by querying its logs.

  This function queries journalctl for neural_executor logs and checks if the
  readiness log message is present, indicating that neural_executor has
  successfully subscribed to /neural/control.

  Returns:
      bool: True if neural_executor is ready, False otherwise
  """
  try:
    # Query journalctl for neural_executor logs
    result = subprocess.run(
      [
        "journalctl",
        "--user",
        "-u",
        "neural_executor.service",
        "-n",
        "100",  # Last 100 lines
        "--output=json",
      ],
      capture_output=True,
      text=True,
    )

    if result.returncode != 0:
      logger.warning(f"journalctl command failed with return code {result.returncode}")
      return False

    # Parse journalctl output
    for line in result.stdout.strip().split("\n"):
      if not line:
        continue

      try:
        log_entry = json.loads(line)
        message = log_entry.get("MESSAGE", "")
        if READINESS_LOG_PATTERN in message:
          logger.info(f"Found readiness log: {message}")
          return True
      except json.JSONDecodeError:
        continue

    logger.info("neural_executor readiness log not found")
    return False

  except FileNotFoundError:
    logger.error("journalctl command not found")
    return False
  except Exception as e:
    logger.error(f"Error checking neural_executor readiness: {e}")
    return False


def get_executor_status() -> Literal["active", "failed", "inactive", "unknown"]:
  """
  Get the current status of neural_executor service.

  Returns:
      Literal["active", "failed", "inactive", "unknown"]: Service status
  """
  try:
    result = subprocess.run(
      ["systemctl", "--user", "show", "-p", "ActiveState", "neural_executor.service"],
      capture_output=True,
      text=True,
    )

    if result.returncode != 0:
      return "unknown"

    # Parse output: "ActiveState=active"
    status_line = result.stdout.strip()
    if "=" in status_line:
      status = status_line.split("=")[1].lower()
      if status in ["active", "failed", "inactive"]:
        return status

    return "unknown"

  except FileNotFoundError:
    logger.error("systemctl command not found")
    return "unknown"
  except Exception as e:
    logger.error(f"Error getting neural_executor status: {e}")
    return "unknown"
