# Scenario: Infer Concats Features in Metadata Order
- Given: VtolNeuralInferenceNode initialized with feature provider and metadata specifying features [a, b, c]
- When: infer() method is called without arguments
- Then: The method returns a concatenated vector with features in exact order [a, b, c]

## Test Steps

- Case 1 (happy path): Infer returns concatenated feature vector for all features in metadata order
- Case 2 (edge case): Infer with single metadata feature returns that feature only
- Case 3 (edge case): Infer with empty metadata returns empty array

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
