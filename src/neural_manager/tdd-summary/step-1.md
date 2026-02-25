# Step 1 - Understand Intent

## Functional Requirements

### FR-1: Configurable Search Paths
ModelDiscoverer should accept a list of search paths where it looks for ONNX models and their metadata files. These paths can be configured at initialization and should support both absolute and relative paths.

### FR-2: Metadata File Discovery with Multiple Strategies
_find_metadata_file() should implement multiple search strategies:
- Task-specific search: Look in task-specific directories first
- Default search: Fall back to default search paths if task-specific search fails
- Return the first valid metadata file found

### FR-3: Auto-Discover and Load Models
discover_and_load() should:
- Automatically find the model file and metadata file without manual path specification
- Use standard search paths to locate files
- Load both the ONNX model and its metadata
- Return a model object with metadata

### FR-4: Optional Model Integrity Verification
_verify_checksum() should:
- Calculate MD5 checksum of the model file using hashlib.md5
- Compare with the checksum from metadata
- Support optional verification (can be disabled if checksum not in metadata)
- Raise error if checksums don't match

### FR-5: List Available Models
list_available_models() should:
- Scan all configured search paths
- Find all metadata files (observation_metadata.yaml)
- Return a list of available model names and their locations
- Provide useful information about discovered models

## Assumptions

- ONNX model files are named `model.onnx`
- Metadata files are named `observation_metadata.yaml`
- Metadata files follow the structure created by ModelWithMetadataExporter (name, version, path, checksum, input_shape, output_shape)
- Search paths are directories, not file paths
- Multiple search paths are searched in order (first match wins)
- Checksum verification is optional and only performed if checksum exists in metadata
- ONNX Runtime is available for loading ONNX models
