# Scenario: Startup Validation Passes with All Features Matching

- Given: An observations_metadata.yaml file with multiple features (e.g., "target_error" dim=3, "gravity_projection" dim=3)
- When: The feature provider has all corresponding methods with matching output dimensions
- Then: Startup validation must pass without raising any errors

## Test Steps

- Case 1 (single feature): One feature with matching dimension
- Case 2 (multiple features): Three features with all matching dimensions
- Case 3 (mixed data types): Features with different dimensions (2, 3, 4) all matching

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
