# Scenario: FeatureSpec Dataclass
- Given: FeatureSpec dataclass is defined
- When: FeatureSpec is instantiated with name, dim, dtype, and description
- Then: FeatureSpec correctly stores all fields and can be converted to/from dict

## Test Steps

- Case 1 (happy path): Create FeatureSpec with valid parameters and verify all fields are stored correctly
- Case 2 (edge case): Verify FeatureSpec works with different dtypes (float32, float64, int32)

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
