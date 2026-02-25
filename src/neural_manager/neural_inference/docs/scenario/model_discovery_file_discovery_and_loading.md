# Scenario: ModelDiscoverer File Discovery and Loading

Test the model discovery and loading functionality.

## Test Steps

### Case 1: Initialization with string paths
- Given: List of string paths to search directories
- When: ModelDiscoverer is initialized with these paths
- Then: Paths are converted to Path objects and stored correctly

### Case 2: Initialization with Path objects
- Given: List of Path objects to search directories
- When: ModelDiscoverer is initialized with these paths
- Then: Paths are stored correctly without conversion

### Case 3: Initialization expands user paths
- Given: List containing "~/path" (user home directory)
- When: ModelDiscoverer is initialized with this path
- Then: Path is expanded to absolute home directory path

### Case 4: Find metadata using default strategy
- Given: Search path containing observation_metadata.yaml
- When: _find_metadata_file() is called without task parameter
- Then: Returns path to observation_metadata.yaml in search path

### Case 5: Find metadata using task-specific strategy
- Given: Search path containing task_name/observation_metadata.yaml
- When: _find_metadata_file() is called with task="task_name"
- Then: Returns path to task_name/observation_metadata.yaml

### Case 6: Find metadata not found
- Given: Search paths without observation_metadata.yaml
- When: _find_metadata_file() is called
- Then: Returns None

### Case 7: List available models (single path)
- Given: Search path with one metadata file
- When: list_available_models() is called
- Then: Returns list with one model entry

### Case 8: List available models (multiple paths)
- Given: Multiple search paths each with metadata files
- When: list_available_models() is called
- Then: Returns list with all unique models (no duplicates)

### Case 9: Load metadata with checksum
- Given: Valid metadata YAML with checksum field
- When: _load_metadata() is called
- Then: Returns ModelMetadata with checksum populated

### Case 10: Load metadata without checksum
- Given: Valid metadata YAML without checksum field
- When: _load_metadata() is called
- Then: Returns ModelMetadata with checksum as None

### Case 11: Load metadata missing required fields
- Given: Metadata YAML missing required fields (e.g., name, version)
- When: _load_metadata() is called
- Then: Should handle missing fields appropriately (raise error or use defaults)

### Case 12: Verify checksum matches
- Given: Model file and metadata with matching MD5 checksum
- When: _verify_checksum() is called
- Then: Returns True without raising error

### Case 13: Verify checksum mismatch
- Given: Model file and metadata with different MD5 checksum
- When: _verify_checksum() is called
- Then: Raises ValueError with checksum mismatch message

### Case 14: Verify checksum None skips verification
- Given: Model file and metadata with checksum=None
- When: _verify_checksum() is called
- Then: Returns True without calculating or comparing checksums

### Case 15: Discover and load valid model
- Given: Search path with valid metadata and model file
- When: discover_and_load() is called
- Then: Returns DiscoveredModel with metadata and ONNX Runtime session

### Case 16: Discover and load metadata not found
- Given: Search paths without metadata file
- When: discover_and_load() is called
- Then: Raises FileNotFoundError

### Case 17: Discover and load model file not found
- Given: Metadata with path to non-existent model file
- When: discover_and_load() is called
- Then: Raises FileNotFoundError

### Case 18: Discover and load checksum mismatch
- Given: Metadata with mismatched checksum
- When: discover_and_load() is called
- Then: Raises ValueError

### Case 19: Calculate MD5 checksum (empty file)
- Given: Empty file
- When: calculate_md5_checksum() is called
- Then: Returns correct MD5 hash for empty file

### Case 20: Calculate MD5 checksum (small file)
- Given: Small file with known content
- When: calculate_md5_checksum() is called
- Then: Returns correct MD5 hash matching expected value

### Case 21: Calculate MD5 checksum (large file)
- Given: Large file (>8KB)
- When: calculate_md5_checksum() is called
- Then: Returns correct MD5 hash (using chunked reading)

### Case 22: Calculate MD5 checksum (file not found)
- Given: Non-existent file path
- When: calculate_md5_checksum() is called
- Then: Raises FileNotFoundError

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
