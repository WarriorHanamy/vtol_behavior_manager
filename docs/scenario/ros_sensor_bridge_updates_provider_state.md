# Scenario: Ros Sensor Bridge Updates Provider State
- Given: RosSensorBridge initialized with VtolFeatureProvider and VtolNeuralInferenceNode
- When: ROS callbacks (odometry, IMU, GPS, inference timer) are triggered
- Then: VtolFeatureProvider state is updated through update methods and infer() produces observations

## Test Steps

- Case 1 (happy path): Odometry callback triggers update_vehicle_odom() and subsequent infer() returns non-empty observation
- Case 2 (edge case): IMU callback triggers update_imu() and get_ang_vel_b() returns correct values
- Case 3 (edge case): GPS callback triggers update_target() and get_to_target_b() works with target data
- Case 4 (edge case): Inference timer callback triggers update_last_action() with control commands

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
