# Scenario: All Features Inference
- Given: VtolNeuralInferenceNode is initialized with feature provider
- When: infer() method is called without a specific feature name (or feature_name=None)
- Then: The method returns a concatenated vector of all features in metadata order

## Test Steps

- Case 1 (happy path): Inference returns concatenated feature vector for all features
- Case 2 (edge case): Some features return None from provider
- Case 3 (edge case): All features return None from provider

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
