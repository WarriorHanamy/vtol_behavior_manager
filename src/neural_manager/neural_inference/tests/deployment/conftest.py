"""
pytest configuration and fixtures for deployment tests.

This module provides common fixtures and configuration for deployment-side unit tests.
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
# This allows importing from features and neural_manager modules
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
