# Scenario: Metadata Loading
- Given: observation_metadata.yaml exists with feature specifications
- When: FeatureProviderBase._load_metadata() is called
- Then: Method parses YAML and returns list of FeatureSpec objects with correct data

## Test Steps

- Case 1 (happy path): Load metadata from valid YAML file with multiple features
- Case 2 (edge case): Load metadata from YAML with single feature
- Case 3 (edge case): Handle missing description field (optional field)

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
