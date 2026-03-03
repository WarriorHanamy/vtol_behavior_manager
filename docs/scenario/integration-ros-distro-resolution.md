# Scenario: Integration - ROS Distro Resolution

- Given: ROS_DISTRO environment variable set to "humble" and `/opt/ros/humble/setup.bash` exists
- When: The wrapper is executed with target script
- Then: The wrapper loads `/opt/ros/humble/setup.bash` when present

## Test Steps

- Case 1 (happy path): Set ROS_DISTRO=humble, create mock setup file, verify it is sourced
- Case 2 (edge case): Unset ROS_DISTRO, verify default humble is used

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
