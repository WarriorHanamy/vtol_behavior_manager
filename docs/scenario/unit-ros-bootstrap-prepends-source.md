# Scenario: Unit - ROS Bootstrap Prepends Source

- Given: The resolver output from `scripts/ros_wrapper.sh` provides setup path
- When: The wrapper builds the final exec command
- Then: The command assembly prepends a source operation before uv invocation

## Test Steps

- Case 1 (happy path): Mock resolved setup path `/opt/ros/humble/setup.bash`, verify `source /opt/ros/humble/setup.bash` appears before `uv run --no-sync python`
- Case 2 (edge case): Mock empty ROS_DISTRO, verify default humble is used and sourced

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
