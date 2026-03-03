# Scenario: Bootstrap Status Marker Output
- Given: Wrapper has --print-paths flag and has attempted ROS bootstrap
- When: Wrapper is executed with --print-paths flag
- Then: Output must contain an explicit bootstrap success or failure marker

## Test Steps

- Case 1 (happy path): Wrapper with --print-paths displays success marker after successful ROS bootstrap (e.g., "ROS_BOOTSTRAP: SUCCESS")
- Case 2 (failure case): Wrapper with --print-paths displays failure marker when ROS setup is missing (e.g., "ROS_BOOTSTRAP: FAILED")

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
