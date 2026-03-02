# Scenario: Startup Validation Fails on Missing Provider Method

- Given: An observations_metadata.yaml file with a feature named "target_error"
- When: The feature provider does not have a `get_target_error()` method
- Then: Startup must fail with an explicit error message about the missing method

## Test Steps

- Case 1 (missing method): Feature "missing_feature" in metadata but no `get_missing_feature()` method exists
- Case 2 (method typo): Feature "target_error" in metadata but method name is `get_target_eror()` (typo)
- Case 3 (completely different): Feature "position" in metadata but only `get_velocity()` method exists

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
