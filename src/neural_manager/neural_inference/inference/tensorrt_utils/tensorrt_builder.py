"""
TensorRT engine builder for neural_pos_ctrl.

This module provides utilities for building TensorRT engines from ONNX models.
TensorRT engines provide optimized inference performance on NVIDIA GPUs.

Usage:
    # Build a TensorRT engine from ONNX model
    success = build_tensorrt_engine(
        onnx_path="models/policy.onnx",
        engine_path="models/policy.trt",
        fp16_mode=True
    )

    # Check if engine exists and is valid
    if engine_exists_and_valid("models/policy.trt", "models/policy.onnx"):
        print("Engine is up to date")

Reference:
    https://docs.nvidia.com/deeplearning/tensorrt/api/python_api/index.html
    https://github.com/NVIDIA/TensorRT/tree/main/samples/python
"""

import hashlib
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import tensorrt as trt
    TRT_AVAILABLE = True
except ImportError:
    TRT_AVAILABLE = False

try:
    import onnx
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False


# =============================================================================
# TensorRT Builder Configuration
# =============================================================================

class BuilderConfig:
    """Configuration for TensorRT engine building."""

    def __init__(
        self,
        max_batch_size: int = 1,
        max_workspace_size: int = 1_000_000_000,  # 1GB
        fp16_mode: bool = True,
        int8_mode: bool = False,
        int8_calibrator: Optional[Any] = None,
        strict_type_constraints: bool = False,
        keep_outputs: bool = False,
    ):
        """
        Initialize builder configuration.

        Args:
            max_batch_size: Maximum batch size for dynamic batching
            max_workspace_size: Maximum GPU workspace size in bytes
            fp16_mode: Enable FP16 precision mode
            int8_mode: Enable INT8 precision mode
            int8_calibrator: INT8 calibrator for quantization
            strict_type_constraints: Use strict type constraints
            keep_outputs: Keep intermediate layer outputs
        """
        self.max_batch_size = max_batch_size
        self.max_workspace_size = max_workspace_size
        self.fp16_mode = fp16_mode
        self.int8_mode = int8_mode
        self.int8_calibrator = int8_calibrator
        self.strict_type_constraints = strict_type_constraints
        self.keep_outputs = keep_outputs

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "max_batch_size": self.max_batch_size,
            "max_workspace_size": self.max_workspace_size,
            "fp16_mode": self.fp16_mode,
            "int8_mode": self.int8_mode,
            "strict_type_constraints": self.strict_type_constraints,
            "keep_outputs": self.keep_outputs,
        }

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'BuilderConfig':
        """Create configuration from dictionary."""
        return cls(**config)

    @classmethod
    def default(cls) -> 'BuilderConfig':
        """Get default builder configuration."""
        return cls(
            max_batch_size=1,
            max_workspace_size=1_000_000_000,
            fp16_mode=True,
            int8_mode=False,
        )

    @classmethod
    def fp16(cls) -> 'BuilderConfig':
        """Get FP16-optimized configuration."""
        return cls(
            max_batch_size=1,
            max_workspace_size=1_000_000_000,
            fp16_mode=True,
            int8_mode=False,
        )

    @classmethod
    def int8(cls, calibrator: Optional[Any] = None) -> 'BuilderConfig':
        """Get INT8-optimized configuration."""
        return cls(
            max_batch_size=1,
            max_workspace_size=1_000_000_000,
            fp16_mode=False,
            int8_mode=True,
            int8_calibrator=calibrator,
        )


# =============================================================================
# Engine Building Functions
# =============================================================================

def build_tensorrt_engine(
    onnx_path: Path,
    engine_path: Path,
    config: Optional[BuilderConfig] = None,
    log_func: Optional[callable] = None,
) -> bool:
    """
    Build a TensorRT engine from an ONNX model.

    Args:
        onnx_path: Path to input ONNX model file
        engine_path: Path to output TensorRT engine file
        config: Builder configuration (uses default if None)
        log_func: Optional logging function (e.g., node_logger.info)

    Returns:
        True if engine built successfully, False otherwise

    Example:
        >>> success = build_tensorrt_engine(
        ...     onnx_path=Path("models/policy.onnx"),
        ...     engine_path=Path("models/policy.trt"),
        ...     config=BuilderConfig.fp16()
        ... )
    """
    if not TRT_AVAILABLE:
        if log_func:
            log_func("TensorRT not available")
        else:
            print("[ERROR] TensorRT not available")
        return False

    if not ONNX_AVAILABLE:
        if log_func:
            log_func("ONNX not available")
        else:
            print("[ERROR] ONNX not available")
        return False

    # Convert to Path objects
    onnx_path = Path(onnx_path)
    engine_path = Path(engine_path)

    # Check if ONNX model exists
    if not onnx_path.exists():
        if log_func:
            log_func(f"ONNX model not found: {onnx_path}")
        else:
            print(f"[ERROR] ONNX model not found: {onnx_path}")
        return False

    # Use default config if not provided
    if config is None:
        config = BuilderConfig.default()

    _log(log_func, f"Building TensorRT engine: {onnx_path} -> {engine_path}")
    _log(log_func, f"  FP16: {config.fp16_mode}, INT8: {config.int8_mode}")

    start_time = time.time()

    try:
        # Create TensorRT logger and builder
        trt_logger = trt.Logger(trt.Logger.INFO)
        builder = trt.Builder(trt_logger)

        # Create network with explicit batch flag
        network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = builder.create_network(network_flags)

        # Create ONNX parser
        parser = trt.OnnxParser(network, trt_logger)

        # Parse ONNX model
        _log(log_func, "  Parsing ONNX model...")
        with open(onnx_path, 'rb') as model:
            if not parser.parse(model.read()):
                error_msg = "Failed to parse ONNX model:"
                for error in range(parser.num_errors):
                    error_msg += f"\n    {parser.get_error(error)}"
                if log_func:
                    log_func(error_msg)
                else:
                    print(f"[ERROR] {error_msg}")
                return False

        _log(log_func, f"  ONNX model parsed successfully")
        _log(log_func, f"  Inputs: {network.num_inputs}, Outputs: {network.num_outputs}")

        # Log input/output information
        for i in range(network.num_inputs):
            input_tensor = network.get_input(i)
            _log(log_func, f"    Input {i}: {input_tensor.name}, shape: {input_tensor.shape}")
        for i in range(network.num_outputs):
            output_tensor = network.get_output(i)
            _log(log_func, f"    Output {i}: {output_tensor.name}, shape: {output_tensor.shape}")

        # Create builder config
        builder_config = builder.create_builder_config()

        # Set workspace size
        builder_config.max_workspace_size = config.max_workspace_size

        # Set FP16 mode
        if config.fp16_mode:
            builder_config.set_flag(trt.BuilderFlag.FP16)

        # Set INT8 mode
        if config.int8_mode:
            builder_config.set_flag(trt.BuilderFlag.INT8)
            if config.int8_calibrator is not None:
                builder_config.int8_calibrator = config.int8_calibrator

        # Set strict type constraints
        if config.strict_type_constraints:
            builder_config.set_flag(trt.BuilderFlag.STRICT_TYPES)

        # Build engine
        _log(log_func, "  Building TensorRT engine...")
        engine = builder.build_engine(network, builder_config)

        if engine is None:
            if log_func:
                log_func("  Failed to build TensorRT engine")
            else:
                print("[ERROR] Failed to build TensorRT engine")
            return False

        # Save engine
        _log(log_func, "  Saving engine...")
        engine_path.parent.mkdir(parents=True, exist_ok=True)
        with open(engine_path, 'wb') as f:
            f.write(engine.serialize())

        elapsed = time.time() - start_time
        _log(log_func, f"  Engine built successfully in {elapsed:.2f}s")

        return True

    except Exception as e:
        if log_func:
            log_func(f"  Error building engine: {e}")
        else:
            print(f"[ERROR] Error building engine: {e}")
        return False


def build_tensorrt_engine_with_fallback(
    onnx_path: Path,
    engine_path: Path,
    config: Optional[BuilderConfig] = None,
    log_func: Optional[callable] = None,
) -> bool:
    """
    Build TensorRT engine with automatic fallback to FP16 if FP8 fails.

    Args:
        onnx_path: Path to input ONNX model file
        engine_path: Path to output TensorRT engine file
        config: Builder configuration
        log_func: Optional logging function

    Returns:
        True if engine built successfully, False otherwise
    """
    if config is None:
        config = BuilderConfig.default()

    # Try building with original config
    if build_tensorrt_engine(onnx_path, engine_path, config, log_func):
        return True

    # Fallback to FP16 only
    if config.fp16_mode and config.int8_mode:
        _log(log_func, "  INT8 build failed, falling back to FP16...")
        fp16_config = BuilderConfig.fp16()
        return build_tensorrt_engine(onnx_path, engine_path, fp16_config, log_func)

    # Fallback to FP32
    if config.fp16_mode:
        _log(log_func, "  FP16 build failed, falling back to FP32...")
        fp32_config = BuilderConfig(
            max_batch_size=config.max_batch_size,
            max_workspace_size=config.max_workspace_size,
            fp16_mode=False,
            int8_mode=False,
        )
        return build_tensorrt_engine(onnx_path, engine_path, fp32_config, log_func)

    return False


# =============================================================================
# Engine Validation Functions
# =============================================================================

def get_model_hash(model_path: Path) -> str:
    """
    Get hash of a model file for version tracking.

    Args:
        model_path: Path to model file (ONNX or TensorRT engine)

    Returns:
        MD5 hash of the file
    """
    model_path = Path(model_path)
    if not model_path.exists():
        return ""

    md5 = hashlib.md5()
    with open(model_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def engine_exists_and_valid(
    engine_path: Path,
    onnx_path: Path,
    check_hash: bool = True,
    log_func: Optional[callable] = None,
) -> bool:
    """
    Check if TensorRT engine exists and matches the ONNX model.

    Args:
        engine_path: Path to TensorRT engine file
        onnx_path: Path to ONNX model file
        check_hash: Whether to check if engine hash matches ONNX hash
        log_func: Optional logging function

    Returns:
        True if engine exists and is valid, False otherwise
    """
    engine_path = Path(engine_path)
    onnx_path = Path(onnx_path)

    # Check if engine file exists
    if not engine_path.exists():
        return False

    # Check if ONNX file exists
    if not onnx_path.exists():
        return False

    # Check hash if requested
    if check_hash:
        engine_hash = get_model_hash(engine_path)
        onnx_hash = get_model_hash(onnx_path)

        # Create a metadata file to store the ONNX hash
        meta_path = engine_path.with_suffix(".meta")

        if meta_path.exists():
            with open(meta_path, 'r') as f:
                stored_onnx_hash = f.read().strip()
            if stored_onnx_hash == onnx_hash:
                return True
            else:
                _log(log_func, f"  Engine outdated (ONNX model changed)")
                return False
        else:
            # No metadata file, assume engine is outdated
            _log(log_func, f"  Engine metadata not found")
            return False

    return True


def update_engine_metadata(
    engine_path: Path,
    onnx_path: Path,
    config: Optional[BuilderConfig] = None,
) -> bool:
    """
    Update engine metadata file with ONNX hash and build config.

    Args:
        engine_path: Path to TensorRT engine file
        onnx_path: Path to ONNX model file
        config: Builder configuration used

    Returns:
        True if metadata updated successfully
    """
    try:
        engine_path = Path(engine_path)
        onnx_path = Path(onnx_path)
        meta_path = engine_path.with_suffix(".meta")

        onnx_hash = get_model_hash(onnx_path)

        with open(meta_path, 'w') as f:
            f.write(f"onnx_hash: {onnx_hash}\n")
            if config is not None:
                f.write(f"config: {config.to_dict()}\n")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to update engine metadata: {e}")
        return False


def build_or_load_engine(
    onnx_path: Path,
    engine_path: Path,
    config: Optional[BuilderConfig] = None,
    force_rebuild: bool = False,
    log_func: Optional[callable] = None,
) -> bool:
    """
    Build TensorRT engine if it doesn't exist or is outdated.

    Args:
        onnx_path: Path to ONNX model file
        engine_path: Path to TensorRT engine file
        config: Builder configuration
        force_rebuild: Force rebuild even if engine exists and is valid
        log_func: Optional logging function

    Returns:
        True if engine is ready to use, False otherwise
    """
    onnx_path = Path(onnx_path)
    engine_path = Path(engine_path)

    if not force_rebuild and engine_exists_and_valid(engine_path, onnx_path, log_func=log_func):
        _log(log_func, f"  Using existing engine: {engine_path}")
        return True

    _log(log_func, f"  Building TensorRT engine...")
    success = build_tensorrt_engine_with_fallback(onnx_path, engine_path, config, log_func)

    if success:
        update_engine_metadata(engine_path, onnx_path, config)

    return success


# =============================================================================
# Utility Functions
# =============================================================================

def _log(log_func: Optional[callable], msg: str):
    """Helper function for logging."""
    if log_func:
        log_func(msg)
    else:
        print(f"[INFO] {msg}")


def get_engine_info(engine_path: Path, log_func: Optional[callable] = None) -> Optional[Dict[str, Any]]:
    """
    Get information about a TensorRT engine.

    Args:
        engine_path: Path to TensorRT engine file
        log_func: Optional logging function

    Returns:
        Dictionary with engine information or None if failed
    """
    if not TRT_AVAILABLE:
        return None

    engine_path = Path(engine_path)
    if not engine_path.exists():
        return None

    try:
        trt_logger = trt.Logger(trt.Logger.INFO)
        runtime = trt.Runtime(trt_logger)

        with open(engine_path, 'rb') as f:
            engine = runtime.deserialize_cuda_engine(f.read())

        if engine is None:
            return None

        info = {
            "num_bindings": engine.num_bindings,
            "max_batch_size": engine.max_batch_size,
            "inputs": [],
            "outputs": [],
        }

        for i in range(engine.num_bindings):
            name = engine.get_binding_name(i)
            shape = engine.get_binding_shape(i)
            dtype = engine.get_binding_dtype(i)
            is_input = engine.binding_is_input(i)

            binding_info = {
                "name": name,
                "shape": tuple(shape),
                "dtype": str(dtype),
            }

            if is_input:
                info["inputs"].append(binding_info)
            else:
                info["outputs"].append(binding_info)

        return info

    except Exception as e:
        if log_func:
            log_func(f"  Error reading engine: {e}")
        else:
            print(f"[ERROR] Error reading engine: {e}")
        return None


def list_available_devices(log_func: Optional[callable] = None) -> List[str]:
    """
    List available CUDA devices for TensorRT.

    Args:
        log_func: Optional logging function

    Returns:
        List of device names
    """
    devices = []

    try:
        import pycuda.driver as cuda
        cuda.init()

        num_gpus = cuda.Device.count()
        for i in range(num_gpus):
            device = cuda.Device(i)
            devices.append(f"{device.name()} ({device.compute_capability()})")

    except Exception as e:
        if log_func:
            log_func(f"  Error listing devices: {e}")
        else:
            print(f"[ERROR] Error listing devices: {e}")

    return devices
