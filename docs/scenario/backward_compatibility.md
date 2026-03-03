# Scenario: Backward Compatibility with Existing Diagnostics
- Given: Wrapper has existing --print-paths output format
- When: Wrapper is executed with --print-paths flag
- Then: All existing diagnostic lines must be preserved without modification

## Test Steps

- Case 1 (happy path): --print-paths output contains all original lines (PYTHON_CMD, ROS_DISTRO, ROS_SETUP, package imports)
- Case 2 (package checks): --print-paths output still contains Python package import verification (onnxruntime, numpy, yaml)

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
