# Scenario: Auto-Discover and Load Models
- Given: A ModelDiscoverer instance with configured search paths
- When: discover_and_load() is called with a model name
- Then: It automatically finds the ONNX model and metadata, loads them, and returns a model object

## Test Steps

- Case 1 (happy path): Model and metadata found in search paths, successfully loaded
- Case 2 (model not found): Model file missing, raises appropriate error
- Case 3 (metadata not found): Metadata file missing, raises appropriate error
- Case 4 (load error): Model file exists but fails to load, raises appropriate error
- Case 5 (partial match): Only metadata found, model file missing, raises error

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
