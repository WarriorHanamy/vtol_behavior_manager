# Scenario: Infer Handles None Features with Zero Padding
- Given: VtolNeuralInferenceNode initialized with feature provider where some feature methods return None
- When: infer() method is called for those features
- Then: The method returns float32 zero vectors with dimensions from metadata

## Test Steps

- Case 1 (happy path): Feature returning None for dim 4 is replaced with zeros(shape=(4,), dtype=float32)
- Case 2 (edge case): Multiple features returning None are all zero-padded correctly
- Case 3 (edge case): All features returning None results in all zero vector with correct total dimension
- Case 4 (edge case): Feature returning valid value is not zero-padded

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
