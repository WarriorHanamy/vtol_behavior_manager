# Scenario: ROS Setup File Discovery
- Given: A resolved ROS distribution name
- When: The wrapper attempts to locate the setup file
- Then: The correct setup file path is constructed and verified

## Test Steps

- Case 1 (file exists): Setup file exists at /opt/ros/humble/setup.bash
- Case 2 (file missing): Setup file does not exist at /opt/ros/humble/setup.bash
- Case 3 (invalid distro): Resolved distro leads to non-existent path

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
