# Scenario: Unit - Bootstrap Failure Exit

- Given: Mock bootstrap failure status from `scripts/ros_wrapper.sh` (missing setup file)
- When: The wrapper attempts to load ROS environment
- Then: The wrapper exits non-zero without executing uv run command

## Test Steps

- Case 1 (happy path): Mock missing setup file at `/opt/ros/humble/setup.bash`, verify wrapper exits with code 1
- Case 2 (edge case): Mock permission denied on setup file, verify wrapper exits non-zero

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
