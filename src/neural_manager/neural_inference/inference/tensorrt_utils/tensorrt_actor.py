"""
TensorRT inference actors for neural_pos_ctrl.

This module provides TensorRT-accelerated inference implementations
for GRU and MLP policy actors using cuda-python for GPU memory management.

TensorRT engines must be built from ONNX models using tensorrt_builder.py
or the NVIDIA trtexec tool.

Reference:
    https://docs.nvidia.com/deeplearning/tensorrt/api/python_api/index.html
    https://nvidia.github.io/cuda-python/cuda-bindings/latest
"""

import time
from pathlib import Path
from typing import Any

import numpy as np

try:
  import tensorrt as trt

  TRT_AVAILABLE = True
except ImportError:
  TRT_AVAILABLE = False

try:
  from cuda.bindings import driver as cu_driver
  from cuda.bindings import runtime as cu_runtime

  CUDA_AVAILABLE = True
except ImportError:
  CUDA_AVAILABLE = False

from inference.actors import BasePolicyActor


class _CudaStream:
  """Wrapper around a CUDA stream created via cuda-python bindings."""

  def __init__(self):
    self._handle = int(cu_driver.cuStreamCreate(0))

  @property
  def handle(self) -> int:
    return self._handle

  def synchronize(self):
    cu_driver.cuStreamSynchronize(self._handle)

  def destroy(self):
    if self._handle != 0:
      cu_driver.cuStreamDestroy(self._handle)
      self._handle = 0


class _CudaDeviceBuffer:
  """Device memory allocation via cuda-python bindings."""

  def __init__(self, nbytes: int):
    self.nbytes = nbytes
    err, self._ptr = cu_driver.cuMemAlloc(nbytes)
    if err != cu_driver.CUresult.CUDA_SUCCESS:
      raise RuntimeError(f"cuMemAlloc failed: {err}")

  @property
  def ptr(self) -> int:
    return int(self._ptr)

  def copy_from_host(self, host_array: np.ndarray):
    cu_driver.cuMemcpyHtoD(self._ptr, host_array.ctypes.data, self.nbytes)

  def copy_to_host(self, host_array: np.ndarray):
    cu_driver.cuMemcpyDtoH(host_array.ctypes.data, self._ptr, self.nbytes)

  def destroy(self):
    if self._ptr != 0:
      cu_driver.cuMemFree(self._ptr)
      self._ptr = 0


def _cuda_init():
  """Initialize CUDA context if not already initialized."""
  if not CUDA_AVAILABLE:
    return
  err = cu_driver.cuInit(0)
  if err != cu_driver.CUresult.CUDA_SUCCESS:
    raise RuntimeError(f"cuInit failed: {err}")


class TensorRTPolicyActor(BasePolicyActor):
  """
  Base class for TensorRT inference actors.

  Provides common functionality for loading TensorRT engines and
  running inference with CUDA streams.

  This class does NOT call BasePolicyActor.__init__ because the base
  class unconditionally creates an ONNX Runtime InferenceSession,
  which is not applicable to TensorRT engines.
  """

  def __init__(
    self,
    engine_path: Path,
    node_logger=None,
    max_batch_size: int = 1,
    enable_fp16: bool = True,
  ):
    """
    Initialize TensorRT policy actor.

    Args:
        engine_path: Path to TensorRT engine file
        node_logger: ROS2 node logger for structured logging
        max_batch_size: Maximum batch size for inference
        enable_fp16: Whether FP16 mode is enabled
    """
    if not TRT_AVAILABLE:
      raise ImportError("TensorRT is not available. Install with: pip install tensorrt-cu12")
    if not CUDA_AVAILABLE:
      raise ImportError("cuda-python is not available. Install with: pip install cuda-python")

    engine_path = Path(engine_path)

    if not engine_path.exists():
      error_msg = f"TensorRT engine not found: {engine_path}"
      if node_logger:
        node_logger.error(error_msg)
      else:
        print(error_msg)
      raise FileNotFoundError(error_msg)

    # Skip BasePolicyActor.__init__ (it loads ONNX).
    # Initialize only the shared bookkeeping fields.
    self._logger = node_logger
    self._inference_count = 0
    self._total_inference_time = 0.0
    self._start_time = time.time()

    self._engine_path = engine_path
    self._max_batch_size = max_batch_size
    self._enable_fp16 = enable_fp16

    self._engine = None
    self._context = None

    self._inputs: list[dict[str, Any]] = []
    self._outputs: list[dict[str, Any]] = []
    self._bindings: list[dict[str, Any]] = []
    self._stream: _CudaStream | None = None
    self._device_buffers: list[_CudaDeviceBuffer] = []
    self._host_buffers: list[np.ndarray] = []

    _cuda_init()
    self._load_engine()

  def _load_engine(self):
    """Load TensorRT engine from file."""
    log_msg = f"Loading TensorRT engine: {self._engine_path}"
    if self._logger:
      self._logger.info(log_msg)
    else:
      print(log_msg)

    trt_logger = trt.Logger(trt.Logger.INFO)

    runtime = trt.Runtime(trt_logger)
    with open(self._engine_path, "rb") as f:
      engine_data = f.read()

    self._engine = runtime.deserialize_cuda_engine(engine_data)

    if self._engine is None:
      error_msg = "Failed to load TensorRT engine"
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      raise RuntimeError(error_msg)

    self._context = self._engine.create_execution_context()

    self._stream = _CudaStream()

    self._setup_bindings()
    self._allocate_buffers()

    device_info = f"TensorRT engine loaded: {self._engine_path}"
    if self._logger:
      self._logger.info(device_info)
    else:
      print(device_info)

  def _setup_bindings(self):
    """Setup input/output bindings for the engine."""
    self._inputs = []
    self._outputs = []
    self._bindings = []

    for i in range(self._engine.num_io_tensors):
      tensor_name = self._engine.get_tensor_name(i)
      tensor_mode = self._engine.get_tensor_mode(tensor_name)
      tensor_shape = self._engine.get_tensor_shape(tensor_name)
      tensor_dtype = self._engine.get_tensor_dtype(tensor_name)

      binding = {
        "name": tensor_name,
        "shape": tuple(tensor_shape),
        "dtype": self._trt_dtype_to_np(tensor_dtype),
        "index": i,
      }

      if tensor_mode == trt.TensorIOMode.INPUT:
        self._inputs.append(binding)
      else:
        self._outputs.append(binding)

      self._bindings.append(binding)

    if self._logger:
      self._logger.info("TensorRT engine I/O:")
      for inp in self._inputs:
        self._logger.info(f"  Input: {inp['name']}, shape: {inp['shape']}, dtype: {inp['dtype']}")
      for out in self._outputs:
        self._logger.info(f"  Output: {out['name']}, shape: {out['shape']}, dtype: {out['dtype']}")
    else:
      print("TensorRT engine I/O:")
      for inp in self._inputs:
        print(f"  Input: {inp['name']}, shape: {inp['shape']}, dtype: {inp['dtype']}")
      for out in self._outputs:
        print(f"  Output: {out['name']}, shape: {out['shape']}, dtype: {out['dtype']}")

  def _trt_dtype_to_np(self, trt_dtype: trt.DataType) -> np.dtype:
    """Convert TensorRT data type to numpy dtype."""
    mapping = {
      trt.DataType.FLOAT32: np.float32,
      trt.DataType.FLOAT16: np.float16,
      trt.DataType.INT8: np.int8,
      trt.DataType.INT32: np.int32,
      trt.DataType.BOOL: np.bool_,
    }
    return mapping.get(trt_dtype, np.float32)

  def _allocate_buffers(self):
    """Allocate CUDA device memory and host numpy buffers for all I/O tensors."""
    self._device_buffers = []
    self._host_buffers = []

    for binding in self._bindings:
      size = trt.volume(self._engine.get_tensor_shape(binding["name"]))
      nbytes = size * binding["dtype"].itemsize

      self._device_buffers.append(_CudaDeviceBuffer(nbytes))
      self._host_buffers.append(np.empty(size, dtype=binding["dtype"]))

  def _copy_input_to_device(self, inputs: dict[str, np.ndarray]):
    """Copy input arrays from host to device."""
    for i, binding in enumerate(self._bindings):
      tensor_name = binding["name"]
      if tensor_name in inputs:
        input_array = inputs[tensor_name].astype(binding["dtype"]).flatten()
        self._host_buffers[i][:] = input_array
        self._device_buffers[i].copy_from_host(self._host_buffers[i])

  def _copy_output_from_device(self) -> dict[str, np.ndarray]:
    """Copy output arrays from device to host."""
    outputs = {}
    output_names = {out["name"] for out in self._outputs}

    for i, binding in enumerate(self._bindings):
      if binding["name"] in output_names:
        self._device_buffers[i].copy_to_host(self._host_buffers[i])
        outputs[binding["name"]] = self._host_buffers[i].reshape(binding["shape"])

    return outputs

  @property
  def input_shape(self) -> tuple[int, ...]:
    """Get expected input shape."""
    if self._inputs:
      return self._inputs[0]["shape"]
    return ()

  @property
  def output_shape(self) -> tuple[int, ...]:
    """Get expected output shape."""
    if self._outputs:
      return self._outputs[0]["shape"]
    return ()

  def __del__(self):
    """Clean up CUDA resources."""
    if self._stream is not None:
      self._stream.destroy()
    for buf in self._device_buffers:
      buf.destroy()


class TensorRTGRUActor(TensorRTPolicyActor):
  """
  GRU-based policy actor using TensorRT engine.

  Handles models with recurrent hidden state (GRU layers).
  Manages hidden state I/O tensors for sequential inference.
  """

  def __init__(
    self,
    engine_path: Path,
    hidden_dim: int = 64,
    num_layers: int = 1,
    node_logger=None,
    expected_input_shape: tuple[int, ...] | None = None,
    expected_output_shape: tuple[int, ...] | None = None,
    max_batch_size: int = 1,
  ):
    super().__init__(engine_path, node_logger, max_batch_size)

    self.hidden_dim = hidden_dim
    self.num_layers = num_layers

    if expected_input_shape is not None or expected_output_shape is not None:
      if not self.validate_shapes(expected_input_shape, expected_output_shape):
        raise ValueError("TensorRT GRU actor shape validation failed")

    self.h_state = np.zeros((num_layers, 1, hidden_dim), dtype=np.float32)

    self._h_state_device = _CudaDeviceBuffer(self.h_state.nbytes)
    self._h_state_device.copy_from_host(self.h_state.flatten())

  def validate_shapes(self, expected_input_shape=None, expected_output_shape=None):
    """Validate model input/output shapes against expected shapes."""
    actual_input_shape = self.input_shape
    actual_output_shape = self.output_shape

    if expected_input_shape is not None and actual_input_shape != expected_input_shape:
      error_msg = (
        f"Input shape mismatch: expected {expected_input_shape}, got {actual_input_shape}"
      )
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    if expected_output_shape is not None and actual_output_shape != expected_output_shape:
      error_msg = (
        f"Output shape mismatch: expected {expected_output_shape}, got {actual_output_shape}"
      )
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    return True

  def reset(self):
    """Reset hidden state."""
    self.h_state = np.zeros((self.num_layers, 1, self.hidden_dim), dtype=np.float32)
    self._h_state_device.copy_from_host(self.h_state.flatten())
    self.reset_stats()

  def __call__(self, obs: np.ndarray) -> np.ndarray:
    """
    Execute inference.

    Args:
        obs: Single observation or batch of observations

    Returns:
        Action(s) from the GRU model
    """
    if obs.ndim == 1:
      obs = obs[None, :]
    obs = obs.astype(np.float32)

    input_name = self._inputs[0]["name"]
    hidden_name = self._inputs[1]["name"] if len(self._inputs) > 1 else "h_state"

    inputs = {
      input_name: obs,
      hidden_name: self.h_state,
    }

    self._copy_input_to_device(inputs)

    for i, binding in enumerate(self._bindings):
      self._context.set_tensor_address(binding["name"], self._device_buffers[i].ptr)

    start_time = time.perf_counter()
    self._context.execute_async_v3(self._stream.handle)
    self._stream.synchronize()
    inference_time = (time.perf_counter() - start_time) * 1000.0

    outputs = self._copy_output_from_device()

    output_name = self._outputs[0]["name"]
    action = outputs[output_name]

    if len(self._outputs) > 1:
      hidden_output_name = self._outputs[1]["name"]
      self.h_state = outputs[hidden_output_name]
      self._h_state_device.copy_from_host(self.h_state.flatten())

    self._log_inference_time(inference_time)

    if action.shape[0] == 1:
      return action.squeeze(0)
    return action


class TensorRTMLPActor(TensorRTPolicyActor):
  """
  MLP-based policy actor using TensorRT engine.

  Handles feedforward models without recurrent state.
  Processes observation history (stacked observations) as input.
  """

  def __init__(
    self,
    engine_path: Path,
    node_logger=None,
    expected_input_shape: tuple[int, ...] | None = None,
    expected_output_shape: tuple[int, ...] | None = None,
    max_batch_size: int = 1,
  ):
    super().__init__(engine_path, node_logger, max_batch_size)

    if expected_input_shape is not None or expected_output_shape is not None:
      if not self.validate_shapes(expected_input_shape, expected_output_shape):
        raise ValueError("TensorRT MLP actor shape validation failed")

  def validate_shapes(self, expected_input_shape=None, expected_output_shape=None):
    """Validate model input/output shapes against expected shapes."""
    actual_input_shape = self.input_shape
    actual_output_shape = self.output_shape

    if expected_input_shape is not None and actual_input_shape != expected_input_shape:
      error_msg = (
        f"Input shape mismatch: expected {expected_input_shape}, got {actual_input_shape}"
      )
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    if expected_output_shape is not None and actual_output_shape != expected_output_shape:
      error_msg = (
        f"Output shape mismatch: expected {expected_output_shape}, got {actual_output_shape}"
      )
      if self._logger:
        self._logger.error(error_msg)
      else:
        print(error_msg)
      return False

    return True

  def reset(self):
    """Reset state (MLP is stateless, so no-op)."""
    self.reset_stats()

  def __call__(self, obs: np.ndarray) -> np.ndarray:
    """
    Execute inference.

    Args:
        obs: Observation history stack, shape (stacked_obs_dim,) or (batch_size, stacked_obs_dim)

    Returns:
        Action, shape (action_dim,) or (batch_size, action_dim)
    """
    if obs.ndim == 1:
      obs = obs[None, :]
    obs = obs.astype(np.float32)

    expected_shape = self.input_shape
    actual_shape = obs.shape

    if len(expected_shape) == 2:
      if actual_shape[1] != expected_shape[1]:
        warning_msg = (
          f"Warning: Input dimension mismatch. Expected {expected_shape}, got {actual_shape}"
        )
        if self._logger:
          self._logger.warning(warning_msg)
        else:
          print(warning_msg)

    input_name = self._inputs[0]["name"]
    inputs = {input_name: obs}

    self._copy_input_to_device(inputs)

    for i, binding in enumerate(self._bindings):
      self._context.set_tensor_address(binding["name"], self._device_buffers[i].ptr)

    start_time = time.perf_counter()
    self._context.execute_async_v3(self._stream.handle)
    self._stream.synchronize()
    inference_time = (time.perf_counter() - start_time) * 1000.0

    outputs = self._copy_output_from_device()

    output_name = self._outputs[0]["name"]
    action = outputs[output_name]

    self._log_inference_time(inference_time)

    if action.shape[0] == 1:
      return action.squeeze(0)
    return action
