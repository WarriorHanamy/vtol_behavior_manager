# Scenario: Graceful None Feature Handling
- Given: VtolNeuralInferenceNode's feature provider returns None for a feature (e.g., sensor data unavailable)
- When: infer() method is called and encounters None feature values
- Then: The method handles None gracefully with zero-padding based on metadata dimensions

## Test Steps

- Case 1 (happy path): Single feature returns None, zero-padded with correct dimension
- Case 2 (happy path): Multiple features return None in all-features inference
- Case 3 (edge case): Zero-padding matches expected dimensions from metadata

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
