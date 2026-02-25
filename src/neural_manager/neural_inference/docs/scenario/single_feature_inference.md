# Scenario: Single Feature Inference
- Given: VtolNeuralInferenceNode is initialized with feature provider
- When: infer() method is called with a specific feature name
- Then: The method returns the computed feature vector for that feature

## Test Steps

- Case 1 (happy path): Inference returns valid feature vector
- Case 2 (edge case): Feature name not found in metadata
- Case 3 (edge case): Feature provider returns None for requested feature

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
