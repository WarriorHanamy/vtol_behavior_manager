# Scenario: Initialization with Configurable Search Paths
- Given: VtolNeuralInferenceNode is being initialized
- When: A list of search paths is provided to the constructor
- Then: ModelDiscoverer is initialized with the provided search paths

## Test Steps

- Case 1 (happy path): Initialize with valid search paths list
- Case 2 (edge case): Initialize with empty search paths list
- Case 3 (edge case): Initialize with single search path

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
