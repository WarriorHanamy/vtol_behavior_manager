# Scenario: ROS_DISTRO Resolution
- Given: A bash environment with or without ROS_DISTRO set
- When: The wrapper script starts
- Then: The correct ROS distribution is selected

## Test Steps

- Case 1 (ROS_DISTRO set): ROS_DISTRO environment variable is set to "foxy"
- Case 2 (ROS_DISTRO unset): ROS_DISTRO environment variable is not set
- Case 3 (ROS_DISTRO empty): ROS_DISTRO environment variable is set but empty

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
