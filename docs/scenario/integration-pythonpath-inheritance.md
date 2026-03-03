# Scenario: Integration - Python Path Inheritance

- Given: ROS environment loaded successfully
- When: Child process is spawned via uv run
- Then: Child process inherits ROS PYTHONPATH values after setup loading

## Test Steps

- Case 1 (happy path): Mock setup file that sets PYTHONPATH, verify child process has PYTHONPATH in environment
- Case 2 (edge case): Mock multiple ROS paths, verify all are inherited

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
