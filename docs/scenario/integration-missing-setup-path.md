# Scenario: Integration - Missing Setup Path

- Given: Setup path derived from ROS_DISTRO does not exist
- When: The wrapper attempts to source the setup file
- Then: Wrapper returns non-zero exit code

## Test Steps

- Case 1 (happy path): Set ROS_DISTRO to non-existent distro, verify wrapper exits with code 1
- Case 2 (edge case): Set ROS_DISTRO to empty string with no default setup file, verify wrapper exits

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
