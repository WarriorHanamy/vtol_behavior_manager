"""
Inference layer components for neural inference module.

This module provides neural network inference functionality including:
- Policy actors (ONNX Runtime and TensorRT)
- Inference providers with automatic fallback
"""

try:
  from .actors import BasePolicyActor, GRUPolicyActor, MLPPolicyActor

  _ACTORS_AVAILABLE = True
except ImportError:
  _ACTORS_AVAILABLE = False
  BasePolicyActor = None  # type: ignore
  GRUPolicyActor = None  # type: ignore
  MLPPolicyActor = None  # type: ignore

try:
  from .inference_provider import (
    InferenceProvider,
    InferenceProviderFactory,
    ONNXProvider,
    TensorRTProvider,
  )

  _PROVIDER_AVAILABLE = True
except ImportError:
  _PROVIDER_AVAILABLE = False
  InferenceProvider = None  # type: ignore
  ONNXProvider = None  # type: ignore
  TensorRTProvider = None  # type: ignore
  InferenceProviderFactory = None  # type: ignore

__all__ = [
  "BasePolicyActor",
  "GRUPolicyActor",
  "MLPPolicyActor",
  "InferenceProvider",
  "ONNXProvider",
  "TensorRTProvider",
  "InferenceProviderFactory",
]
