# Scenario: VtolFeatureProvider Feature Calculations

Test the VTOL-specific feature provider implementation.

## Test Steps

### Case 1: Initialization with valid metadata
- Given: Valid observation_metadata.yaml with VTOL features
- When: VtolFeatureProvider is initialized with this metadata path
- Then: Initialization succeeds and base class validation runs

### Case 2: Initialization creates sensor buffers
- Given: VtolFeatureProvider is initialized
- When: Checking sensor buffer attributes
- Then: All sensor buffers (_position_ned, _velocity_ned, _quat, _ang_vel_frd, _target_pos_ned, _last_action) are None

### Case 3: Initialization calls base validation
- Given: VtolFeatureProvider with metadata requiring methods
- When: VtolFeatureProvider is initialized
- Then: Base class validation runs and prints validation report

### Case 4: Update vehicle odometry stores data
- Given: VtolFeatureProvider instance
- When: update_vehicle_odom() is called with position, velocity, quaternion, angular velocity
- Then: All four buffers are updated with provided data (as float32)

### Case 5: Update IMU stores angular velocity
- Given: VtolFeatureProvider instance
- When: update_imu() is called with linear_accel and ang_vel
- Then: _ang_vel_frd buffer is updated with ang_vel (as float32)

### Case 6: Update target stores position
- Given: VtolFeatureProvider instance
- When: update_target() is called with target position
- Then: _target_pos_ned buffer is updated with target position (as float32)

### Case 7: Update last action stores action
- Given: VtolFeatureProvider instance
- When: update_last_action() is called with action vector
- Then: _last_action buffer is updated with action vector (as float32)

### Case 8: _ensure_float32 conversion
- Given: Input array of various dtypes (float64, int32, etc.)
- When: _ensure_float32() is called
- Then: Returns array with dtype float32

### Case 9: get_to_target_b with valid data
- Given: VtolFeatureProvider with position, target position, and quaternion set
- When: get_to_target_b() is called
- Then: Returns target error vector in FLU frame (NED->FRD->FLU transformation applied)

### Case 10: get_to_target_b missing position returns None
- Given: VtolFeatureProvider with target position and quaternion but missing position
- When: get_to_target_b() is called
- Then: Returns None

### Case 11: get_to_target_b missing target returns None
- Given: VtolFeatureProvider with position and quaternion but missing target position
- When: get_to_target_b() is called
- Then: Returns None

### Case 12: get_to_target_b missing quaternion returns None
- Given: VtolFeatureProvider with position and target position but missing quaternion
- When: get_to_target_b() is called
- Then: Returns None

### Case 13: get_to_target_b missing all returns None
- Given: VtolFeatureProvider with no sensor data
- When: get_to_target_b() is called
- Then: Returns None

### Case 14: get_grav_dir_b with valid quaternion
- Given: VtolFeatureProvider with quaternion set
- When: get_grav_dir_b() is called
- Then: Returns normalized gravity direction vector in FLU frame

### Case 15: get_grav_dir_b missing quaternion returns None
- Given: VtolFeatureProvider with no quaternion
- When: get_grav_dir_b() is called
- Then: Returns None

### Case 16: get_grav_dir_b returns normalized vector
- Given: VtolFeatureProvider with quaternion set
- When: get_grav_dir_b() is called
- Then: Returns vector with unit norm (approximately 1.0)

### Case 17: get_ang_vel_b with valid data
- Given: VtolFeatureProvider with angular velocity set
- When: get_ang_vel_b() is called
- Then: Returns angular velocity in FLU frame (FRD->FLU transformation applied)

### Case 18: get_ang_vel_b missing data returns None
- Given: VtolFeatureProvider with no angular velocity
- When: get_ang_vel_b() is called
- Then: Returns None

### Case 19: get_ang_vel_b transforms FRD to FLU
- Given: VtolFeatureProvider with angular velocity [1, 2, 3] in FRD frame
- When: get_ang_vel_b() is called
- Then: Returns angular velocity [1, -2, -3] in FLU frame (Y and Z negated)

### Case 20: get_last_action with valid data
- Given: VtolFeatureProvider with last action set
- When: get_last_action() is called
- Then: Returns the buffered action vector

### Case 21: get_last_action no buffer returns None
- Given: VtolFeatureProvider with no action buffered
- When: get_last_action() is called
- Then: Returns None

### Case 22: _ned_to_frd identity quaternion
- Given: Identity quaternion [1, 0, 0, 0] and vector [x, y, z]
- When: _ned_to_frd() is called
- Then: Returns unchanged vector [x, y, z]

### Case 23: _ned_to_frd rotation
- Given: Rotation quaternion and vector
- When: _ned_to_frd() is called
- Then: Returns correctly rotated vector using quaternion active rotation

### Case 24: _frd_to_flu negates Y and Z
- Given: Vector [x, y, z] in FRD frame
- When: _frd_to_flu() is called
- Then: Returns vector [x, -y, -z] in FLU frame

### Case 25: _frd_to_flu preserves X
- Given: Vector [x, y, z] in FRD frame
- When: _frd_to_flu() is called
- Then: X component remains unchanged

### Case 26: None handling for all get methods
- Given: VtolFeatureProvider with no sensor data
- When: All get methods are called
- Then: All methods return None gracefully

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
