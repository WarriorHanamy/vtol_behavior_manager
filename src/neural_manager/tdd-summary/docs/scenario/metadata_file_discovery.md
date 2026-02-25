# Scenario: Metadata File Discovery with Multiple Strategies
- Given: A ModelDiscoverer instance with configured search paths
- When: _find_metadata_file() is called with or without task specification
- Then: It uses multiple search strategies and returns the first valid metadata file

## Test Steps

- Case 1 (task-specific found): Task-specific directory contains metadata, returns it
- Case 2 (task-specific not found, default found): Task-specific not found, falls back to default paths
- Case 3 (both found): Both task-specific and default found, task-specific takes precedence
- Case 4 (not found): No metadata file found in any search path, returns None
- Case 5 (invalid metadata): Metadata file exists but is malformed, handled gracefully

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
