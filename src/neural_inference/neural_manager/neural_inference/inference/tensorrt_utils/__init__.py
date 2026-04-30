"""TensorRT utilities for neural inference.

This module provides TensorRT-accelerated inference implementations.
TensorRT engines must be built from ONNX models using tensorrt_builder.py.
"""

from .tensorrt_actor import (
    CUDA_AVAILABLE,
    TRT_AVAILABLE,
    TensorRTGRUActor,
    TensorRTMLPActor,
    TensorRTPolicyActor,
)
from .tensorrt_builder import (
    ONNX_AVAILABLE,
    BuilderConfig,
    build_or_load_engine,
    build_tensorrt_engine,
    build_tensorrt_engine_with_fallback,
    engine_exists_and_valid,
    get_engine_info,
    get_model_hash,
    list_available_devices,
)
from .tensorrt_builder import (
    TRT_AVAILABLE as BUILDER_TRT_AVAILABLE,
)

__all__ = [
    # Actors
    "TensorRTPolicyActor",
    "TensorRTGRUActor",
    "TensorRTMLPActor",
    # Builder
    "BuilderConfig",
    "build_tensorrt_engine",
    "build_tensorrt_engine_with_fallback",
    "build_or_load_engine",
    "engine_exists_and_valid",
    "get_model_hash",
    "get_engine_info",
    "list_available_devices",
    # Availability flags
    "TRT_AVAILABLE",
    "CUDA_AVAILABLE",
    "BUILDER_TRT_AVAILABLE",
    "ONNX_AVAILABLE",
]
