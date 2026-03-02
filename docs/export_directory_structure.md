# Standardized Export Directory Structure

This document defines the standardized directory structure for exported policies that vtol-interface can discover by task type.

## Overview

Exported policies are stored in a standardized directory hierarchy under `~/policy_exports`. Each task type has its own subdirectory containing the ONNX model and metadata files.

## Directory Structure

```
~/policy_exports/
├── hover/
│   ├── model.onnx
│   └── observation_metadata.yaml
├── nav/
│   ├── model.onnx
│   └── observation_metadata.yaml
├── track/
│   ├── model.onnx
│   └── observation_metadata.yaml
└── collision_avoidance/
    ├── model.onnx
    └── observation_metadata.yaml
```

## Task Directory Definitions

| Task Directory | Purpose | Experiment Names |
|----------------|---------|------------------|
| `hover/` | Stationary hover control | `rec-Vtol-Hover`, `rec-Vtol-Hover-Play` |
| `nav/` | Point-to-point navigation | `rec-Vtol-Nav`, `rec-Vtol-Nav-Play` |
| `track/` | Track/route following | Future: `rec-Vtol-Track` |
| `collision_avoidance/` | Obstacle avoidance navigation | `rec-Vtol-Collision-Avoidance`, `rec-Vtol-Collision-Avoidance-Play`, `rec-Vtol-Collision-Avoidance-MLP`, `rec-Vtol-Collision-Avoidance-MLP-Play` |

## File Specifications

### model.onnx
- ONNX format neural network model
- Exported from PyTorch using `torch.onnx.export`
- Opset version: 11 or higher
- Dynamic batch dimension supported

### observation_metadata.yaml
- YAML format metadata file
- Contains model information and feature specifications

Required fields:
```yaml
name: string              # Model name
version: string           # Model version (semver recommended)
path: string              # Relative path to model.onnx
checksum: string | null   # MD5 checksum for integrity verification
input_shape: list[int]    # Model input tensor shape
output_shape: list[int]   # Model output tensor shape
features:                 # Optional: feature names for observation
  - feature_name_1
  - feature_name_2
  - ...
```

Example:
```yaml
name: vtol-hover-v1.0.0
version: 1.0.0
path: model.onnx
checksum: a1b2c3d4e5f6...
input_shape: [1, 12]
output_shape: [1, 4]
features:
  - position_error
  - velocity
  - attitude
  - angular_velocity
```

## Experiment Name Mapping

### Hover Task
| Experiment Name | Task Directory | Description |
|-----------------|----------------|-------------|
| `rec-Vtol-Hover` | `hover/` | Training environment |
| `rec-Vtol-Hover-Play` | `hover/` | Play/inference environment |

### Navigation Task
| Experiment Name | Task Directory | Description |
|-----------------|----------------|-------------|
| `rec-Vtol-Nav` | `nav/` | Training environment |
| `rec-Vtol-Nav-Play` | `nav/` | Play/inference environment |

### Track Task
| Experiment Name | Task Directory | Description |
|-----------------|----------------|-------------|
| `rec-Vtol-Track` | `track/` | Future: Track following |

### Collision Avoidance Task
| Experiment Name | Task Directory | Description |
|-----------------|----------------|-------------|
| `rec-Vtol-Collision-Avoidance` | `collision_avoidance/` | Training environment (CNN) |
| `rec-Vtol-Collision-Avoidance-Play` | `collision_avoidance/` | Play/inference environment (CNN) |
| `rec-Vtol-Collision-Avoidance-MLP` | `collision_avoidance/` | Training environment (MLP) |
| `rec-Vtol-Collision-Avoidance-MLP-Play` | `collision_avoidance/` | Play/inference environment (MLP) |

## Model Discovery

The vtol-interface `ModelDiscoverer` searches for models in the following order:

1. **Task-specific path**: `~/policy_exports/{task_name}/observation_metadata.yaml`
2. **Default path**: `~/policy_exports/observation_metadata.yaml`

### Usage Example

```python
from neural_manager.model_discovery import ModelDiscoverer

# Initialize with default export directory
discoverer = ModelDiscoverer(
    search_paths=['~/policy_exports']
)

# Discover hover task model
model = discoverer.discover_and_load(model_name='hover')

# Discover collision_avoidance task model
model = discoverer.discover_and_load(model_name='collision_avoidance')

# List all available models
models = discoverer.list_available_models()
```

## Export Workflow

1. **Train model** using drone_racer sweep scripts
2. **Export model** using `export_model_with_metadata` from `tools/training_post/model_metadata_exporter.py`
3. **Place files** in appropriate task directory under `~/policy_exports/`
4. **Verify** using `ModelDiscoverer.list_available_models()`

### Export Command Example

```bash
# Export hover model
./agent_bins/py_exec scripts/rec/export_model_with_metadata.py \
    --checkpoint path/to/checkpoint.pt \
    --output ~/policy_exports/hover \
    --name vtol-hover-v1.0.0 \
    --version 1.0.0

# Export collision_avoidance model
./agent_bins/py_exec scripts/rec/export_model_with_metadata.py \
    --checkpoint path/to/checkpoint.pt \
    --output ~/policy_exports/collision_avoidance \
    --name vtol-collision-v1.0.0 \
    --version 1.0.0
```

## Best Practices

1. **Versioning**: Use semantic versioning for model names (e.g., `vtol-hover-v1.2.3`)
2. **Checksums**: Always include MD5 checksums for integrity verification
3. **Backup**: Keep backup copies of production models
4. **Documentation**: Update this document when adding new task types

## Related Documentation

- [Model Discovery Module](../src/neural_manager/model_discovery.py)
- [Model Metadata Exporter](../../drone_racer/tools/training_post/model_metadata_exporter.py)
- [MUST_KNOW - VTOL-Interface](./MUST_KNOW.md)