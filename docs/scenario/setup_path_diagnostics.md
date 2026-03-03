# Scenario: Setup Script Path Diagnostics Output
- Given: Wrapper has --print-paths flag
- When: Wrapper is executed with --print-paths flag after successful ROS bootstrap
- Then: Output must contain a line with resolved setup script absolute path

## Test Steps

- Case 1 (happy path): Wrapper with --print-paths displays setup path with absolute path (e.g., "ROS_SETUP: /opt/ros/humble/setup.bash")
- Case 2 (edge case): Wrapper with --print-paths displays setup path when using custom distro (e.g., "ROS_SETUP: /opt/ros/noetic/setup.bash")

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
