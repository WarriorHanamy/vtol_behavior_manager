# Scenario: Get Single Feature
- Given: FeatureProviderBase is initialized with metadata and implementations
- When: FeatureProviderBase.get_feature() is called with a feature name
- Then: Method returns the feature vector with error checking for invalid names

## Test Steps

- Case 1 (happy path): Get valid feature by name
- Case 2 (edge case): Attempt to get invalid feature name (should raise error)
- Case 3 (edge case): Get feature with specific dimension to verify correctness

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
