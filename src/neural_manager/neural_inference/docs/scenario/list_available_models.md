# Scenario: List Available Models
- Given: VtolNeuralInferenceNode is initialized with search paths
- When: list_available_models() method is called
- Then: The method returns a list of available models by delegating to ModelDiscoverer

## Test Steps

- Case 1 (happy path): Returns list of available models from search paths
- Case 2 (edge case): Returns empty list when no models found
- Case 3 (edge case): Returns correct model information including name, version, path

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
