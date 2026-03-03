# Scenario: Infer Raises Error for Missing Feature
- Given: VtolNeuralInferenceNode initialized with feature provider and metadata
- When: infer(feature_name) is called with a feature_name not in metadata
- Then: The method raises ValueError listing available features

## Test Steps

- Case 1 (happy path): Infer with unknown feature name raises ValueError with feature list
- Case 2 (edge case): Infer with None feature_name retrieves all features (no error)
- Case 3 (edge case): Infer with valid feature_name retrieves that feature only

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
