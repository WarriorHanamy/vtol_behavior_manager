# Scenario: Failure Handling
- Given: ROS setup file is missing or invalid
- When: The wrapper attempts to source the setup file
- Then: Appropriate error message is displayed and script exits with non-zero code

## Test Steps

- Case 1 (missing setup file): /opt/ros/humble/setup.bash does not exist
- Case 2 (missing with custom distro): /opt/ros/foxy/setup.bash does not exist when ROS_DISTRO=foxy
- Case 3 (file not readable): Setup file exists but is not readable (permission denied)

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
