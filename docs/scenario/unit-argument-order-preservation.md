# Scenario: Unit - Argument Order Preservation

- Given: Mock argv `['script.py','--flag','value']` provided to wrapper
- When: The wrapper argument builder processes the argv after bootstrap stage
- Then: The wrapper returns the same ordered argv after bootstrap stage

## Test Steps

- Case 1 (happy path): Input argv `['script.py','--flag','value']`, verify output preserves exact order
- Case 2 (edge case): Input argv `['script.py','-x','-y','arg']`, verify long and short flags preserved
- Case 3 (edge case): Input argv with `--print-paths`, verify flag removed before uv invocation

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
