# Scenario: Convention-Based Discovery
- Given: FeatureProviderBase has subclasses with get_{feature_name} methods
- When: FeatureProviderBase._validate_implementations() is called
- Then: Method discovers and validates all feature implementations against metadata

## Test Steps

- Case 1 (happy path): Validate subclass with all required feature methods implemented
- Case 2 (edge case): Detect missing feature method (validation should fail)
- Case 3 (edge case): Detect dimension mismatch (implementation returns wrong size)

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
