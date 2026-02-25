# Scenario: Configurable Search Paths
- Given: A ModelDiscoverer instance is initialized with a list of search paths
- When: The discoverer searches for models
- Then: It searches only in the configured paths in the specified order

## Test Steps

- Case 1 (happy path): Multiple search paths configured, model found in second path
- Case 2 (single path): Single search path configured, model found in that path
- Case 3 (empty paths): Empty search paths list, no models found
- Case 4 (relative paths): Relative paths are properly resolved to absolute paths
- Case 5 (invalid paths): Invalid paths are handled gracefully without errors

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
