# Scenario: Automatic Model Discovery and Feature Provider Initialization
- Given: VtolNeuralInferenceNode is initialized with search paths and valid models exist
- When: Constructor is called without task_name (or with optional task_name)
- Then: ModelDiscoverer discovers the model and VtolFeatureProvider is initialized with the model's metadata

## Test Steps

- Case 1 (happy path): Automatic discovery and initialization without task_name
- Case 2 (happy path): Automatic discovery and initialization with task_name
- Case 3 (edge case): Model discovery fails (no metadata found)

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
