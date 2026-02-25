# MUST-KNOW - VTOL-Interface Submodule

This document specifies Python environment and critical information for running vtol-interface submodule.

## Python Environment

### Python Version
- **System Python**: \`3.10.12\` (\`/usr/bin/python3.10\`)
- **Required**: \`3.10.0\` or higher
- **Recommended**: Use project's Python 3.10 via uv

### How Python is Selected

The vtol-interface uses \`uv run --no-sync python\` to use the project's Python 3.10 environment.

**Important**: Always use \`project_bins/python_entry_point\` wrapper to run tests or scripts.

**Note**: Unlike drone_racer, vtol-interface does NOT use \`isaaclab.sh\` or system Python directly. It uses uv-managed Python 3.10.

### Python Entry Point

\`\`\`bash
# Always use the wrapper
./project_bins/python_entry_point --version
./project_bins/python_entry_point --print-paths

# Run tests
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/deployment/
\`\`\`

## Dependencies

### Required Python Packages

Use \`uv pip install\` or rely on \`pyproject.toml\`:
\`\`\`bash
# From vtol-interface directory
uv pip install onnxruntime numpy pyyaml
\`\`\`

- \`onnxruntime\` - ONNX model inference
- \`numpy\` - Numerical computing
- \`pyyaml\` - YAML configuration parsing

### Optional Python Packages (Development)
- \`pytest\` - Testing framework
- \`pytest-cov\` - Test coverage
- \`ruff\` - Linting and formatting
- \`mypy\` - Static type checking

## Running Tests

**IMPORTANT**: Always use \`project_bins/python_entry_point\` to run tests.

\`\`\`bash
# Run all deployment tests
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/deployment/

# Run with coverage
./project_bins/python_entry_point pytest --cov=vtol-interface/src --cov-report=html src/neural_manager/neural_inference/tests/deployment/

# Run specific test file
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/deployment/test_feature_provider_base.py
\`\`\`

### Integration Tests

\`\`\`bash
# Run integration tests
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/integration/
\`\`\`

**Note**: All tests can run independently without IsaacLab dependencies.

## File Structure Highlights

| Directory | Purpose | Dependencies |
|-----------|---------|--------------|
| \`src/features/\` | Feature provider framework | Pure Python |
| \`src/neural_manager/neural_inference/\` | Neural inference | onnxruntime, numpy |
| \`src/neural_manager/...\` | Other neural manager modules | Various |
| \`src/px4_msgs/msg\` | PX4 message definitions | Generated |
| \`src/px4-ros2-interface-lib/\` | PX4 ROS2 interface | px4_msgs, ROS2 |

## Quick Start

### Feature Provider Testing
\`\`\`bash
# Test FeatureProviderBase
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/deployment/test_feature_provider_base.py

# Test VtolFeatureProvider
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/deployment/test_vtol_feature_provider.py
\`\`\`

### Model Discovery Testing
\`\`\`bash
# Test ModelDiscoverer
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/deployment/test_model_discovery.py
\`\`\`

### Integration Testing
\`\`\`bash
# Test end-to-end pipeline
./project_bins/python_entry_point pytest src/neural_manager/neural_inference/tests/integration/test_end_to_end_export.py
\`\`\`

## Development Notes

### Linting
\`\`\`bash
# Check code style
ruff check src/

# Format code
ruff format src/
\`\`\`

### Type Checking
\`\`\`bash
# Run static type checking
mypy src/
\`\`\`

## Known Issues

### Import Paths
- Imports within vtol-interface should use relative imports: \`from ... import ...\`
- When running tests from repository root, use: \`python -m pytest\`

### Model Loading
- ONNX models are expected in standard search paths:
  - \`../models/\` (relative to repository root)
  - \`/opt/vtol/models/\` (system path)
  - \`~/.vtol/models/\` (user home path)
- See \`ModelDiscoverer\` documentation for search order

### Feature Conventions
- Feature names in \`observation_metadata.yaml\` map to method names: \`get_{feature_name}()\`
- All features must be implemented in platform-specific provider classes
- Validation runs at initialization, not at runtime

## Differences from drone_racer

| Aspect | drone_racer | vtol-interface |
|--------|-----------|----------------|
| Python Version | 3.11.0+ | 3.10.0+ (managed by uv) |
| Python Selection | Uses \`python_entry_point\` wrapper with \`get_python_path()\` | Uses \`python_entry_point\` wrapper with \`uv run --no-sync python\` |
| IsaacLab | Required for core functionality | Not required |
| Testing | Uses \`python_entry_point pytest\` | Uses \`python_entry_point pytest\` |
| Dependencies | IsaacLab + standard libs | Standard Python libs only |

## Notes

- This submodule is IsaacLab-independent
- All tests can run without IsaacLab environment
- **Python version: 3.10.x (managed by uv)**
- **Python entry point: \`project_bins/python_entry_point\`**
- Always use \`python_entry_point\` wrapper to run scripts or tests
- See README.md in this submodule for more details
