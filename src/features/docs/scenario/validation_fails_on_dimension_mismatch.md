# Scenario: Startup Validation Fails on Dimension Mismatch

- Given: An observations_metadata.yaml file with a feature "target_error" of dimension 3
- When: The provider's `get_target_error()` method returns a vector of dimension 2
- Then: Startup must fail with an explicit error message about dimension mismatch

## Test Steps

- Case 1 (wrong dimension): Feature expects dimension 3 but provider returns dimension 2
- Case 2 (extra dimension): Feature expects dimension 2 but provider returns dimension 5
- Case 3 (scalar vs vector): Feature expects dimension 3 but provider returns scalar (dimension 1)

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
