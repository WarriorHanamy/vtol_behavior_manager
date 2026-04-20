import time
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import onnxruntime as ort


class BasePolicyActor(ABC):
  """Base class for policy actors using ONNX models."""

  def __init__(self, onnx_path, providers=None, node_logger=None):
    """Initialize base policy actor.

    Args:
        onnx_path: Path to the ONNX model
        providers: List of execution providers, defaults to CUDA then CPU
        node_logger: ROS2 node logger for structured logging

    """
    # Convert to Path object if needed
    model_path = Path(onnx_path)

    # Check if model file exists
    if not model_path.exists():
      error_msg = f"模型文件不存在: {model_path}"
      if node_logger:
        node_logger.error(error_msg)
      else:
        print(error_msg)
      raise FileNotFoundError(error_msg)

    if providers is None:
      providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    self._logger = node_logger
    self._inference_count = 0
    self._total_inference_time = 0.0
    self._start_time = time.time()

    # Log model loading
    log_msg = f"加载ONNX模型: {model_path}"
    if self._logger:
      self._logger.info(log_msg)
    else:
      print(log_msg)

    # Try to load model with specified providers, fallback to CPU if needed
    try:
      self.session = ort.InferenceSession(str(model_path), providers=providers)
    except Exception as e:
      error_msg = f"Error loading ONNX model with providers {providers}: {e}"
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      print("Falling back to CPUExecutionProvider...")
      self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    # Log current device for debugging
    device_info = f"Policy loaded on: {self.session.get_providers()[0]}"
    if self._logger:
      self._logger.info(device_info)
    else:
      print(device_info)

  @abstractmethod
  def reset(self):
    """Reset actor state (if any)."""
    pass

  @abstractmethod
  def __call__(self, obs):
    """Perform inference.

    Args:
        obs: Observation(s) to process

    Returns:
        Action(s) from the model

    """
    pass

  def _prepare_observation(self, obs):
    """Prepare observation for inference by adding batch dimension if needed.

    Args:
        obs: Input observation(s)

    Returns:
        Prepared observation as float32 numpy array

    """
    if obs.ndim == 1:
      obs = obs[None, :]  # Add batch dimension
    return obs.astype(np.float32)

  def _log_inference_time(self, inference_time_ms: float):
    """Log inference performance metrics.

    Args:
        inference_time_ms: Inference time in milliseconds

    """
    self._inference_count += 1
    self._total_inference_time += inference_time_ms

    log_msg = f"🧠 神经网络推理耗时: {inference_time_ms:.2f} ms"
    if self._logger:
      self._logger.info(log_msg)
    else:
      print(log_msg)

  def get_inference_stats(self) -> dict:
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


class GRUPolicyActor(BasePolicyActor):
  def __init__(
    self,
    onnx_path,
    hidden_dim=64,
    num_layers=1,
    providers=None,
    node_logger=None,
    expected_input_shape=None,
    expected_output_shape=None,
  ):
    """GRU Policy Actor for models with hidden state.

    Args:
        onnx_path: Model path
        hidden_dim: GRU hidden layer dimension
        num_layers: Number of GRU layers
        providers: List of execution providers, defaults to CUDA
        node_logger: ROS2 node logger for structured logging
        expected_input_shape: Expected input shape (tuple), required for validation
        expected_output_shape: Expected output shape (tuple), required for validation

    """
    super().__init__(onnx_path, providers, node_logger)

    self.hidden_dim = hidden_dim
    self.num_layers = num_layers

    # Get input/output information for validation
    input_info = self.session.get_inputs()[0]
    output_info = self.session.get_outputs()[0]
    self.input_name = input_info.name
    self.output_name = output_info.name
    self.input_shape = input_info.shape
    self.output_shape = output_info.shape

    # Log model information
    if self._logger:
      self._logger.info("GRU执行器模型信息:")
      self._logger.info(f"  输入: {input_info.name}, 形状: {input_info.shape}")
      self._logger.info(f"  输出: {output_info.name}, 形状: {output_info.shape}")
    else:
      print("GRU执行器模型信息:")
      print(f"  输入: {input_info.name}, 形状: {input_info.shape}")
      print(f"  输出: {output_info.name}, 形状: {output_info.shape}")

    # Explicit shape validation (required)
    if expected_input_shape is not None or expected_output_shape is not None:
      if not self.validate_shapes(expected_input_shape, expected_output_shape):
        raise ValueError("GRU actor shape validation failed")

    # 初始化隐藏状态
    self.h_state = np.zeros((self.num_layers, 1, self.hidden_dim), dtype=np.float32)

  def validate_shapes(self, expected_input_shape=None, expected_output_shape=None):
    """Validate model input/output shapes against expected shapes."""
    if expected_input_shape is not None and self.input_shape != expected_input_shape:
      error_msg = f"输入形状不匹配，期望 {expected_input_shape}，实际 {self.input_shape}"
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    if expected_output_shape is not None and self.output_shape != expected_output_shape:
      error_msg = f"输出形状不匹配，期望 {expected_output_shape}，实际 {self.output_shape}"
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    return True

  def reset(self):
    """重置隐藏状态"""
    self.h_state = np.zeros((self.num_layers, 1, self.hidden_dim), dtype=np.float32)
    self.reset_stats()

  def __call__(self, obs):
    """执行推理

    Args:
        obs: Single observation or batch of observations

    Returns:
        Action(s) from the GRU model

    """
    obs = self._prepare_observation(obs)

    inputs = {
      self.session.get_inputs()[0].name: obs,
      self.session.get_inputs()[1].name: self.h_state,
    }

    # 运行推理并计时
    start_time = time.perf_counter()
    action, h_out = self.session.run(None, inputs)
    inference_time = (time.perf_counter() - start_time) * 1000.0  # Convert to milliseconds

    # 【关键步骤】自动更新隐藏状态，供下一帧使用
    self.h_state = h_out

    # 记录推理时间
    self._log_inference_time(inference_time)

    # 如果输出是 (1, action_dim)，通常 squeeze 掉 batch 维度返回 (action_dim,)
    # 方便直接传给 gym env，视具体需求而定
    return action.squeeze(0)


class MLPPolicyActor(BasePolicyActor):
  def __init__(
    self,
    onnx_path,
    providers=None,
    node_logger=None,
    expected_input_shape=None,
    expected_output_shape=None,
  ):
    """MLP Policy Actor for models with stacked observation history

    This actor handles MLP models that process concatenated observation history
    rather than single observations. The input dimension is expected to be
    (history_length * single_obs_dim).

    Args:
        onnx_path: 模型路径
        providers: 执行提供者列表，默认优先使用 CUDA
        node_logger: ROS2 node logger for structured logging
        expected_input_shape: Expected input shape (tuple), required for validation
        expected_output_shape: Expected output shape (tuple), required for validation

    """
    super().__init__(onnx_path, providers, node_logger)

    # Get input/output information for validation
    self.input_info = self.session.get_inputs()[0]
    self.output_info = self.session.get_outputs()[0]
    self.input_name = self.input_info.name
    self.expected_input_shape = self.input_info.shape
    self.expected_output_shape = self.output_info.shape

    # Log model information
    if self._logger:
      self._logger.info("MLP执行器模型信息:")
      self._logger.info(f"  输入: {self.input_info.name}, 形状: {self.input_info.shape}")
      self._logger.info(f"  输出: {self.output_info.name}, 形状: {self.output_info.shape}")
    else:
      print("MLP执行器模型信息:")
      print(f"  输入: {self.input_info.name}, 形状: {self.input_info.shape}")
      print(f"  输出: {self.output_info.name}, 形状: {self.output_info.shape}")

    # Explicit shape validation (required)
    if expected_input_shape is not None or expected_output_shape is not None:
      if not self.validate_shapes(expected_input_shape, expected_output_shape):
        raise ValueError("MLP actor shape validation failed")

  def validate_shapes(self, expected_input_shape=None, expected_output_shape=None):
    """Validate model input/output shapes against expected shapes."""
    if expected_input_shape is not None and self.expected_input_shape != expected_input_shape:
      error_msg = f"输入形状不匹配，期望 {expected_input_shape}，实际 {self.expected_input_shape}"
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    if expected_output_shape is not None and self.expected_output_shape != expected_output_shape:
      error_msg = (
        f"输出形状不匹配，期望 {expected_output_shape}，实际 {self.expected_output_shape}"
      )
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    return True

  def reset(self):
    """重置状态 (MLP无状态，所以为空操作)"""
    self.reset_stats()

  def __call__(self, obs):
    """执行推理

    Args:
        obs: 观测值历史堆叠，可以是 (stacked_obs_dim,) 或 (batch_size, stacked_obs_dim)
            其中 stacked_obs_dim = history_length * single_obs_dim

    Returns:
        action: 动作值，形状为 (action_dim,) 或 (batch_size, action_dim)

    """
    obs = self._prepare_observation(obs)

    # Validate input shape
    expected_shape = self.expected_input_shape
    actual_shape = obs.shape

    # Allow flexible batch dimension (1 or None)
    if len(expected_shape) == 2:
      if actual_shape[1] != expected_shape[1]:
        warning_msg = (
          f"Warning: Input dimension mismatch. Expected {expected_shape}, got {actual_shape}"
        )
        if self._logger:
          self._logger.warning(warning_msg)
        else:
          print(warning_msg)
        shape_msg = f"Model expects {expected_shape[1]} input features, got {actual_shape[1]}"
        if self._logger:
          self._logger.warning(shape_msg)
        else:
          print(shape_msg)

    # MLP模型只需要观测历史堆叠输入，无隐藏状态
    inputs = {self.input_name: obs}

    # 运行推理并计时
    start_time = time.perf_counter()
    action = self.session.run(None, inputs)[0]
    inference_time = (time.perf_counter() - start_time) * 1000.0  # Convert to milliseconds

    # 记录推理时间
    self._log_inference_time(inference_time)

    # If output is (1, action_dim), squeeze out batch dimension
    if action.shape[0] == 1:
      return action.squeeze(0)
    return action
