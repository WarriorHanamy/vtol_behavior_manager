"""Inference provider abstraction for neural_pos_ctrl.

This module provides a unified interface for different inference backends
(ONNX Runtime, TensorRT) with automatic fallback support.

Architecture:
    InferenceProvider (ABC)
        ├── ONNXProvider (ONNX Runtime backend)
        └── TensorRTProvider (TensorRT backend)

    InferenceProviderFactory creates providers with fallback chain:
        TensorRT → ONNX CUDA → ONNX CPU
"""

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np


class InferenceProvider(ABC):
  """Abstract base class for inference backends.

  All inference providers must implement this interface to ensure
  compatibility with the neural control pipeline.
  """

  def __init__(self, model_path: Path, node_logger=None):
    """Initialize the inference provider.

    Args:
        model_path: Path to the model file (ONNX or TensorRT engine)
        node_logger: ROS2 node logger for structured logging

    """
    self._model_path = Path(model_path)
    self._logger = node_logger
    self._inference_count = 0
    self._total_inference_time = 0.0
    self._start_time = time.time()

  @abstractmethod
  def load_model(self) -> bool:
    """Load the model from disk.

    Returns:
        True if model loaded successfully, False otherwise

    """
    pass

  @abstractmethod
  def infer(self, observation: np.ndarray) -> np.ndarray:
    """Run inference on an observation.

    Args:
        observation: Input observation array

    Returns:
        Action array from the model

    """
    pass

  @abstractmethod
  def reset(self):
    """Reset any internal state (e.g., hidden states for RNNs)."""
    pass

  @abstractmethod
  def get_input_shape(self) -> tuple[int, ...]:
    """Get expected input shape.

    Returns:
        Tuple of input dimensions

    """
    pass

  @abstractmethod
  def get_output_shape(self) -> tuple[int, ...]:
    """Get expected output shape.

    Returns:
        Tuple of output dimensions

    """
    pass

  def _log_info(self, msg: str):
    """Log info message."""
    if self._logger:
      self._logger.info(msg)
    else:
      print(f"[INFO] {msg}")

  def _log_warning(self, msg: str):
    """Log warning message."""
    if self._logger:
      self._logger.warning(msg)
    else:
      print(f"[WARNING] {msg}")

  def _log_error(self, msg: str):
    """Log error message."""
    if self._logger:
      self._logger.error(msg)
    else:
      print(f"[ERROR] {msg}")

  def _log_inference_time(self, inference_time_ms: float):
    """Log inference performance metrics.

    Args:
        inference_time_ms: Inference time in milliseconds

    """
    self._inference_count += 1
    self._total_inference_time += inference_time_ms

    log_msg = f"🧠 Neural network inference time: {inference_time_ms:.2f} ms"
    self._log_info(log_msg)

  def get_inference_stats(self) -> dict[str, Any]:
    """Get inference performance statistics.

    Returns:
        Dictionary containing inference statistics

    """
    current_time = time.time()
    uptime = current_time - self._start_time

    return {
      "inference_count": self._inference_count,
      "total_inference_time": self._total_inference_time,
      "average_inference_time": self._total_inference_time / max(self._inference_count, 1),
      "inference_rate": self._inference_count / uptime if uptime > 0 else 0.0,
      "uptime_seconds": uptime,
    }

  def reset_stats(self):
    """Reset inference statistics."""
    self._inference_count = 0
    self._total_inference_time = 0.0
    self._start_time = time.time()


class ONNXProvider(InferenceProvider):
  """ONNX Runtime inference provider.

  Wraps the existing ONNX actor implementations (GRUPolicyActor, MLPPolicyActor)
  to provide a unified interface.
  """

  def __init__(
    self,
    onnx_path: Path,
    actor_type: str = "mlp",
    providers: list[str] | None = None,
    hidden_dim: int = 64,
    num_layers: int = 1,
    expected_input_shape: tuple[int, ...] | None = None,
    expected_output_shape: tuple[int, ...] | None = None,
    node_logger=None,
  ):
    """Initialize ONNX Runtime provider.

    Args:
        onnx_path: Path to ONNX model file
        actor_type: Type of actor ("gru" or "mlp")
        providers: List of ONNX execution providers
        hidden_dim: Hidden state dimension for GRU
        num_layers: Number of GRU layers
        expected_input_shape: Expected input shape for validation
        expected_output_shape: Expected output shape for validation
        node_logger: ROS2 node logger

    """
    super().__init__(onnx_path, node_logger)

    self._actor_type = actor_type
    self._actor = None
    self._actor_config = {
      "hidden_dim": hidden_dim,
      "num_layers": num_layers,
      "expected_input_shape": expected_input_shape,
      "expected_output_shape": expected_output_shape,
    }

    if providers is None:
      providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    self._providers = providers

    # Import actors module
    try:
      from inference.actors import GRUPolicyActor, MLPPolicyActor

      self._gru_actor_class = GRUPolicyActor
      self._mlp_actor_class = MLPPolicyActor
    except ImportError:
      self._log_error("Failed to import actor classes")
      raise

  def load_model(self) -> bool:
    """Load ONNX model and initialize actor."""
    try:
      if self._actor_type == "gru":
        self._actor = self._gru_actor_class(
          self._model_path,
          providers=self._providers,
          node_logger=self._logger,
          **self._actor_config,
        )
      elif self._actor_type == "mlp":
        self._actor = self._mlp_actor_class(
          self._model_path,
          providers=self._providers,
          node_logger=self._logger,
          **self._actor_config,
        )
      else:
        self._log_error(f"Unknown actor type: {self._actor_type}")
        return False

      self._log_info(f"ONNX model loaded: {self._model_path}")
      return True

    except Exception as e:
      self._log_error(f"Failed to load ONNX model: {e}")
      return False

  def infer(self, observation: np.ndarray) -> np.ndarray:
    """Run inference using ONNX actor."""
    if self._actor is None:
      raise RuntimeError("Model not loaded. Call load_model() first.")

    return self._actor(observation)

  def reset(self):
    """Reset actor state."""
    if self._actor is not None:
      self._actor.reset()

  def get_input_shape(self) -> tuple[int, ...]:
    """Get expected input shape."""
    if self._actor is None:
      raise RuntimeError("Model not loaded")
    return self._actor.input_shape if hasattr(self._actor, "input_shape") else ()

  def get_output_shape(self) -> tuple[int, ...]:
    """Get expected output shape."""
    if self._actor is None:
      raise RuntimeError("Model not loaded")
    return self._actor.output_shape if hasattr(self._actor, "output_shape") else ()

  @property
  def actor(self):
    """Get the underlying actor instance."""
    return self._actor


class TensorRTProvider(InferenceProvider):
  """TensorRT inference provider.

  Provides TensorRT-accelerated inference for deployment.
  Falls back gracefully if TensorRT is not available.
  """

  def __init__(
    self,
    engine_path: Path,
    actor_type: str = "mlp",
    hidden_dim: int = 64,
    num_layers: int = 1,
    expected_input_shape: tuple[int, ...] | None = None,
    expected_output_shape: tuple[int, ...] | None = None,
    node_logger=None,
  ):
    """Initialize TensorRT provider.

    Args:
        engine_path: Path to TensorRT engine file
        actor_type: Type of actor ("gru" or "mlp")
        hidden_dim: Hidden state dimension for GRU
        num_layers: Number of GRU layers
        expected_input_shape: Expected input shape for validation
        expected_output_shape: Expected output shape for validation
        node_logger: ROS2 node logger

    """
    super().__init__(engine_path, node_logger)

    self._actor_type = actor_type
    self._actor = None
    self._actor_config = {
      "hidden_dim": hidden_dim,
      "num_layers": num_layers,
      "expected_input_shape": expected_input_shape,
      "expected_output_shape": expected_output_shape,
    }

    # Try to import TensorRT actor
    try:
      from inference.tensorrt_utils.tensorrt_actor import (
        TensorRTGRUActor,
        TensorRTMLPActor,
      )

      self._gru_actor_class = TensorRTGRUActor
      self._mlp_actor_class = TensorRTMLPActor
      self._trt_available = True
    except ImportError:
      self._log_warning("TensorRT actor not available, will use ONNX fallback")
      self._trt_available = False

  def load_model(self) -> bool:
    """Load TensorRT engine and initialize actor."""
    if not self._trt_available:
      self._log_error("TensorRT not available")
      return False

    if not self._model_path.exists():
      self._log_error(f"TensorRT engine not found: {self._model_path}")
      return False

    try:
      if self._actor_type == "gru":
        self._actor = self._gru_actor_class(
          self._model_path, node_logger=self._logger, **self._actor_config
        )
      elif self._actor_type == "mlp":
        self._actor = self._mlp_actor_class(
          self._model_path, node_logger=self._logger, **self._actor_config
        )
      else:
        self._log_error(f"Unknown actor type: {self._actor_type}")
        return False

      self._log_info(f"TensorRT engine loaded: {self._model_path}")
      return True

    except Exception as e:
      self._log_error(f"Failed to load TensorRT engine: {e}")
      return False

  def infer(self, observation: np.ndarray) -> np.ndarray:
    """Run inference using TensorRT actor."""
    if self._actor is None:
      raise RuntimeError("Model not loaded. Call load_model() first.")

    return self._actor(observation)

  def reset(self):
    """Reset actor state."""
    if self._actor is not None:
      self._actor.reset()

  def get_input_shape(self) -> tuple[int, ...]:
    """Get expected input shape."""
    if self._actor is None:
      raise RuntimeError("Model not loaded")
    return self._actor.input_shape if hasattr(self._actor, "input_shape") else ()

  def get_output_shape(self) -> tuple[int, ...]:
    """Get expected output shape."""
    if self._actor is None:
      raise RuntimeError("Model not loaded")
    return self._actor.output_shape if hasattr(self._actor, "output_shape") else ()


class InferenceProviderFactory:
  """Factory for creating inference providers with automatic fallback.

  Fallback chain:
      1. TensorRT (if engine exists and available)
      2. ONNX Runtime CUDA (if GPU available)
      3. ONNX Runtime CPU (always available)

  Usage:
      provider = InferenceProviderFactory.create_provider(
          preferred_backends=["tensorrt", "onnx_cuda", "onnx_cpu"],
          model_path=Path("models/policy.onnx"),
          engine_path=Path("models/policy.trt"),
          actor_type="mlp",
          config={...}
      )
  """

  @staticmethod
  def create_provider(
    preferred_backends: list[str],
    model_path: Path,
    actor_type: str = "mlp",
    engine_path: Path | None = None,
    hidden_dim: int = 64,
    num_layers: int = 1,
    expected_input_shape: tuple[int, ...] | None = None,
    expected_output_shape: tuple[int, ...] | None = None,
    node_logger=None,
  ) -> InferenceProvider | None:
    """Create an inference provider with automatic fallback.

    Args:
        preferred_backends: List of backend preferences in order
        model_path: Path to ONNX model file
        actor_type: Type of actor ("gru" or "mlp")
        engine_path: Path to TensorRT engine file
        hidden_dim: Hidden state dimension for GRU
        num_layers: Number of GRU layers
        expected_input_shape: Expected input shape
        expected_output_shape: Expected output shape
        node_logger: ROS2 node logger

    Returns:
        InferenceProvider instance or None if all backends fail

    """
    if engine_path is None:
      # Default engine path next to ONNX model
      engine_path = model_path.with_suffix(".trt")

    for backend in preferred_backends:
      provider = None

      if backend == "tensorrt":
        provider = TensorRTProvider(
          engine_path=engine_path,
          actor_type=actor_type,
          hidden_dim=hidden_dim,
          num_layers=num_layers,
          expected_input_shape=expected_input_shape,
          expected_output_shape=expected_output_shape,
          node_logger=node_logger,
        )

      elif backend in ("onnx_cuda", "onnx"):
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        provider = ONNXProvider(
          onnx_path=model_path,
          actor_type=actor_type,
          providers=providers,
          hidden_dim=hidden_dim,
          num_layers=num_layers,
          expected_input_shape=expected_input_shape,
          expected_output_shape=expected_output_shape,
          node_logger=node_logger,
        )

      elif backend == "onnx_cpu":
        providers = ["CPUExecutionProvider"]
        provider = ONNXProvider(
          onnx_path=model_path,
          actor_type=actor_type,
          providers=providers,
          hidden_dim=hidden_dim,
          num_layers=num_layers,
          expected_input_shape=expected_input_shape,
          expected_output_shape=expected_output_shape,
          node_logger=node_logger,
        )

      # Try to load the model
      if provider is not None and provider.load_model():
        return provider

    # All backends failed
    if node_logger:
      node_logger.error("Failed to initialize any inference backend")
    else:
      print("[ERROR] Failed to initialize any inference backend")

    return None

  @staticmethod
  def get_default_backends() -> list[str]:
    """Get default backend preference list.

    Returns:
        List of backend names in preference order

    """
    return ["tensorrt", "onnx_cuda", "onnx_cpu"]

  @staticmethod
  def get_cpu_only_backends() -> list[str]:
    """Get CPU-only backend list.

    Returns:
        List of CPU-only backends

    """
    return ["onnx_cpu"]
