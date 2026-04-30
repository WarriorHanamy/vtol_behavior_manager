"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Feature Provider Package
"""

from .feature_provider_base import (
  FeatureProviderBase,
  FeatureSpec,
  FeatureValidationResult,
)
from .revision_context import RevisionContext
from .revision_discoverer import RevisionDiscoverer
from .vtol_acro_feature_provider import VtolAcroFeatureProvider
from .vtol_hover_feature_provider import VtolHoverFeatureProvider

# Backward compatibility alias
VtolFeatureProvider = VtolHoverFeatureProvider

__all__ = [
  "FeatureProviderBase",
  "FeatureSpec",
  "FeatureValidationResult",
  "RevisionContext",
  "RevisionDiscoverer",
  "VtolAcroFeatureProvider",
  "VtolFeatureProvider",
  "VtolHoverFeatureProvider",
]
