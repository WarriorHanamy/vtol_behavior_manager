"""Tests for neural executor readiness checker."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestExecutorReadinessChecker:
  """Tests for checking neural_executor readiness via journalctl."""

  def test_check_executor_ready_success(self, monkeypatch):
    """Test successful readiness detection when executor logs subscription message."""
    # Mock subprocess.run to return the expected log message
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = (
      '{"MESSAGE": "Neural: Subscribed to /neural/control (VehicleThrustAccSetpoint)", "SERVICE": "neural_executor"}\n'
    )

    monkeypatch.setattr("subprocess.run", MagicMock(return_value=mock_result))

    # Import after monkeypatch to ensure the subprocess is mocked
    from src.neural_manager.neural_inference.readiness_checker import check_executor_ready

    result = check_executor_ready()
    assert result is True

  def test_check_executor_ready_no_subscription(self, monkeypatch):
    """Test failure when executor doesn't log subscription message."""
    # Mock subprocess to return other logs but not subscription message
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"MESSAGE": "Starting neural executor", "SERVICE": "neural_executor"}\n{"MESSAGE": "Some other log", "SERVICE": "neural_executor"}\n'

    monkeypatch.setattr("subprocess.run", MagicMock(return_value=mock_result))

    from src.neural_manager.neural_inference.readiness_checker import check_executor_ready

    # Should return False when subscription message not found
    result = check_executor_ready()
    assert result is False

  def test_check_executor_ready_journalctl_failure(self, monkeypatch):
    """Test graceful handling of journalctl subprocess failure."""
    # Mock subprocess to fail
    mock_result = MagicMock()
    mock_result.returncode = 1  # Non-zero return code

    monkeypatch.setattr("subprocess.run", MagicMock(return_value=mock_result))

    from src.neural_manager.neural_inference.readiness_checker import check_executor_ready

    # Should return False on journalctl failure
    result = check_executor_ready()
    assert result is False
