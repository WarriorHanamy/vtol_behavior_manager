# Scenario: Get All Features
- Given: FeatureProviderBase is initialized with metadata and implementations
- When: FeatureProviderBase.get_all_features() is called
- Then: Method returns concatenated features in metadata order as numpy array

## Test Steps

- Case 1 (happy path): Get all features from provider with multiple features
- Case 2 (edge case): Get all features from provider with single feature
- Case 3 (edge case): Verify order matches metadata specification

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
