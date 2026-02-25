"""
TensorRT inference actors for neural_pos_ctrl.

This module provides TensorRT-accelerated inference implementations
for GRU and MLP policy actors.

TensorRT engines must be built from ONNX models using tensorrt_builder.py
or the NVIDIA trtexec tool.

Reference:
    https://docs.nvidia.com/deeplearning/tensorrt/api/python_api/index.html
"""

import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import numpy as np

try:
    import tensorrt as trt

    TRT_AVAILABLE = True
except ImportError:
    TRT_AVAILABLE = False

try:
    import pycuda.driver as cuda
    import pycuda.autoinit

    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False

from inference.actors import BasePolicyActor


class TensorRTPolicyActor(BasePolicyActor):
    """
    Base class for TensorRT inference actors.

    Provides common functionality for loading TensorRT engines and
    running inference with CUDA streams.
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
            engine_path: Path to TensorRT engine file (.trt)
            node_logger: ROS2 node logger for structured logging
            max_batch_size: Maximum batch size for inference
            enable_fp16: Whether FP16 mode is enabled
        """
        if not TRT_AVAILABLE:
            raise ImportError(
                "TensorRT is not available. Install with: pip install nvidia-tensorrt"
            )

        # Convert to Path object if needed
        engine_path = Path(engine_path)

        # Check if engine file exists
        if not engine_path.exists():
            error_msg = f"TensorRT engine not found: {engine_path}"
            if node_logger:
                node_logger.error(error_msg)
            else:
                print(error_msg)
            raise FileNotFoundError(error_msg)

        # Initialize base class (with dummy ONNX path for compatibility)
        # Note: We're not actually loading ONNX here, but BasePolicyActor
        # expects a path argument
        super().__init__(engine_path, providers=None, node_logger=node_logger)

        self._logger = node_logger
        self._engine_path = engine_path
        self._max_batch_size = max_batch_size
        self._enable_fp16 = enable_fp16

        # TensorRT components
        self._engine = None
        self._context = None
        self._cuda_ctx = None

        # I/O bindings
        self._inputs: List[Dict[str, Any]] = []
        self._outputs: List[Dict[str, Any]] = []
        self._bindings: List[int] = []
        self._stream = None

        # Load engine
        self._load_engine()

    def _load_engine(self):
        """Load TensorRT engine from file."""
        log_msg = f"Loading TensorRT engine: {self._engine_path}"
        if self._logger:
            self._logger.info(log_msg)
        else:
            print(log_msg)

        # Create TRT logger
        trt_logger = trt.Logger(trt.Logger.INFO)

        # Load engine
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

        # Create CUDA stream if available
        if CUDA_AVAILABLE:
            self._stream = cuda.Stream()

        # Setup I/O bindings
        self._setup_bindings()

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

        # Log I/O information
        if self._logger:
            self._logger.info("TensorRT engine I/O:")
            for inp in self._inputs:
                self._logger.info(
                    f"  Input: {inp['name']}, shape: {inp['shape']}, dtype: {inp['dtype']}"
                )
            for out in self._outputs:
                self._logger.info(
                    f"  Output: {out['name']}, shape: {out['shape']}, dtype: {out['dtype']}"
                )
        else:
            print("TensorRT engine I/O:")
            for inp in self._inputs:
                print(
                    f"  Input: {inp['name']}, shape: {inp['shape']}, dtype: {inp['dtype']}"
                )
            for out in self._outputs:
                print(
                    f"  Output: {out['name']}, shape: {out['shape']}, dtype: {out['dtype']}"
                )

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
        """Allocate CUDA memory for input/output buffers."""
        buffers = []

        for binding in self._bindings:
            # Calculate size
            size = trt.volume(self._engine.get_tensor_shape(binding["name"]))

            # Allocate device memory
            d_buffer = cuda.mem_alloc(size * binding["dtype"].itemsize)

            # Allocate host memory
            h_buffer = np.empty(size, dtype=binding["dtype"])

            buffers.append(
                {
                    "host": h_buffer,
                    "device": d_buffer,
                    "binding": binding,
                }
            )

        return buffers

    def _copy_input_to_device(self, buffers: List[Dict], inputs: Dict[str, np.ndarray]):
        """Copy input arrays from host to device."""
        for buffer in buffers:
            binding = buffer["binding"]
            tensor_name = binding["name"]

            if tensor_name in inputs:
                # Ensure input is contiguous and correct dtype
                input_array = inputs[tensor_name].astype(binding["dtype"])
                buffer["host"][:] = input_array.flatten()
                cuda.memcpy_htod(buffer["device"], buffer["host"])

    def _copy_output_from_device(self, buffers: List[Dict]) -> Dict[str, np.ndarray]:
        """Copy output arrays from device to host."""
        outputs = {}

        for buffer in buffers:
            binding = buffer["binding"]
            tensor_name = binding["name"]

            # Check if this is an output
            is_output = (
                self._engine.get_tensor_mode(tensor_name) == trt.TensorIOMode.OUTPUT
            )

            if is_output:
                cuda.memcpy_dtoh(buffer["host"], buffer["device"])
                outputs[tensor_name] = buffer["host"].reshape(binding["shape"])

        return outputs

    @property
    def input_shape(self) -> Tuple[int, ...]:
        """Get expected input shape."""
        if self._inputs:
            return self._inputs[0]["shape"]
        return ()

    @property
    def output_shape(self) -> Tuple[int, ...]:
        """Get expected output shape."""
        if self._outputs:
            return self._outputs[0]["shape"]
        return ()

    def __del__(self):
        """Clean up CUDA resources."""
        if self._stream is not None and CUDA_AVAILABLE:
            self._stream.detach()


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
        expected_input_shape: Optional[Tuple[int, ...]] = None,
        expected_output_shape: Optional[Tuple[int, ...]] = None,
        max_batch_size: int = 1,
    ):
        """
        Initialize TensorRT GRU actor.

        Args:
            engine_path: Path to TensorRT engine file
            hidden_dim: GRU hidden state dimension
            num_layers: Number of GRU layers
            node_logger: ROS2 node logger
            expected_input_shape: Expected input shape for validation
            expected_output_shape: Expected output shape for validation
            max_batch_size: Maximum batch size
        """
        super().__init__(engine_path, node_logger, max_batch_size)

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # Validate shapes if provided
        if expected_input_shape is not None or expected_output_shape is not None:
            if not self.validate_shapes(expected_input_shape, expected_output_shape):
                raise ValueError("TensorRT GRU actor shape validation failed")

        # Initialize hidden state
        self.h_state = np.zeros((num_layers, 1, hidden_dim), dtype=np.float32)

        # Allocate persistent CUDA memory for hidden state
        if CUDA_AVAILABLE:
            self._h_state_device = cuda.mem_alloc(self.h_state.nbytes)
            # Copy initial hidden state to device
            cuda.memcpy_htod(self._h_state_device, self.h_state)

        # Allocate buffers once
        self._buffers = self._allocate_buffers()

    def validate_shapes(self, expected_input_shape=None, expected_output_shape=None):
        """Validate model input/output shapes against expected shapes."""
        actual_input_shape = self.input_shape
        actual_output_shape = self.output_shape

        if (
            expected_input_shape is not None
            and actual_input_shape != expected_input_shape
        ):
            error_msg = f"输入形状不匹配，期望 {expected_input_shape}，实际 {actual_input_shape}"
            if self._logger:
                self._logger.error(error_msg)
            else:
                print(error_msg)
            return False

        if (
            expected_output_shape is not None
            and actual_output_shape != expected_output_shape
        ):
            error_msg = f"输出形状不匹配，期望 {expected_output_shape}，实际 {actual_output_shape}"
            if self._logger:
                self._logger.error(error_msg)
            else:
                print(error_msg)
            return False

        return True

    def reset(self):
        """重置隐藏状态"""
        self.h_state = np.zeros((self.num_layers, 1, self.hidden_dim), dtype=np.float32)
        if CUDA_AVAILABLE:
            cuda.memcpy_htod(self._h_state_device, self.h_state)
        self.reset_stats()

    def __call__(self, obs: np.ndarray) -> np.ndarray:
        """
        执行推理

        Args:
            obs: Single observation or batch of observations

        Returns:
            Action(s) from the GRU model
        """
        # Prepare observation
        if obs.ndim == 1:
            obs = obs[None, :]  # Add batch dimension
        obs = obs.astype(np.float32)

        # Prepare inputs
        input_name = self._inputs[0]["name"]
        hidden_name = self._inputs[1]["name"] if len(self._inputs) > 1 else "h_state"

        inputs = {
            input_name: obs,
            hidden_name: self.h_state,
        }

        # Copy inputs to device
        self._copy_input_to_device(self._buffers, inputs)

        # Set tensor addresses
        for i, buffer in enumerate(self._buffers):
            self._context.set_tensor_address(
                buffer["binding"]["name"], int(buffer["device"])
            )

        # Run inference
        start_time = time.perf_counter()
        self._context.execute_async_v3(self._stream.handle)
        self._stream.synchronize()
        inference_time = (time.perf_counter() - start_time) * 1000.0

        # Copy outputs from device
        outputs = self._copy_output_from_device(self._buffers)

        # Get output action
        output_name = self._outputs[0]["name"]
        action = outputs[output_name]

        # Update hidden state if available
        if len(self._outputs) > 1:
            hidden_output_name = self._outputs[1]["name"]
            self.h_state = outputs[hidden_output_name]
            if CUDA_AVAILABLE:
                cuda.memcpy_htod(self._h_state_device, self.h_state)

        # Log inference time
        self._log_inference_time(inference_time)

        # Squeeze batch dimension if present
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
        expected_input_shape: Optional[Tuple[int, ...]] = None,
        expected_output_shape: Optional[Tuple[int, ...]] = None,
        max_batch_size: int = 1,
    ):
        """
        Initialize TensorRT MLP actor.

        Args:
            engine_path: Path to TensorRT engine file
            node_logger: ROS2 node logger
            expected_input_shape: Expected input shape for validation
            expected_output_shape: Expected output shape for validation
            max_batch_size: Maximum batch size
        """
        super().__init__(engine_path, node_logger, max_batch_size)

        # Validate shapes if provided
        if expected_input_shape is not None or expected_output_shape is not None:
            if not self.validate_shapes(expected_input_shape, expected_output_shape):
                raise ValueError("TensorRT MLP actor shape validation failed")

        # Allocate buffers once
        self._buffers = self._allocate_buffers()

    def validate_shapes(self, expected_input_shape=None, expected_output_shape=None):
        """Validate model input/output shapes against expected shapes."""
        actual_input_shape = self.input_shape
        actual_output_shape = self.output_shape

        if (
            expected_input_shape is not None
            and actual_input_shape != expected_input_shape
        ):
            error_msg = f"输入形状不匹配，期望 {expected_input_shape}，实际 {actual_input_shape}"
            if self._logger:
                self._logger.error(error_msg)
            else:
                print(error_msg)
            return False

        if (
            expected_output_shape is not None
            and actual_output_shape != expected_output_shape
        ):
            error_msg = f"输出形状不匹配，期望 {expected_output_shape}，实际 {actual_output_shape}"
            if self._logger:
                self._logger.error(error_msg)
            else:
                print(error_msg)
            return False

        return True

    def reset(self):
        """重置状态 (MLP无状态，所以为空操作)"""
        self.reset_stats()

    def __call__(self, obs: np.ndarray) -> np.ndarray:
        """
        执行推理

        Args:
            obs: 观测值历史堆叠，可以是 (stacked_obs_dim,) 或 (batch_size, stacked_obs_dim)

        Returns:
            action: 动作值，形状为 (action_dim,) 或 (batch_size, action_dim)
        """
        # Prepare observation
        if obs.ndim == 1:
            obs = obs[None, :]  # Add batch dimension
        obs = obs.astype(np.float32)

        # Validate input shape
        expected_shape = self.input_shape
        actual_shape = obs.shape

        # Allow flexible batch dimension (1 or None)
        if len(expected_shape) == 2:
            if actual_shape[1] != expected_shape[1]:
                warning_msg = f"Warning: Input dimension mismatch. Expected {expected_shape}, got {actual_shape}"
                if self._logger:
                    self._logger.warning(warning_msg)
                else:
                    print(warning_msg)

        # Prepare input
        input_name = self._inputs[0]["name"]
        inputs = {input_name: obs}

        # Copy input to device
        self._copy_input_to_device(self._buffers, inputs)

        # Set tensor addresses
        for buffer in self._buffers:
            self._context.set_tensor_address(
                buffer["binding"]["name"], int(buffer["device"])
            )

        # Run inference
        start_time = time.perf_counter()
        self._context.execute_async_v3(self._stream.handle)
        self._stream.synchronize()
        inference_time = (time.perf_counter() - start_time) * 1000.0

        # Copy output from device
        outputs = self._copy_output_from_device(self._buffers)

        # Get output action
        output_name = self._outputs[0]["name"]
        action = outputs[output_name]

        # Log inference time
        self._log_inference_time(inference_time)

        # Squeeze batch dimension if present
        if action.shape[0] == 1:
            return action.squeeze(0)
        return action
