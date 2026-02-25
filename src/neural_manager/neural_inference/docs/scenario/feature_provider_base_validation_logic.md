# Scenario: FeatureProviderBase Validation Logic

Test the base class validation and metadata loading functionality.

## Test Steps

### Case 1: Load valid metadata with all required fields
- Given: A valid observation_metadata.yaml with features containing name, dim, and dtype fields
- When: FeatureProviderBase is initialized with this metadata path
- Then: Metadata is loaded correctly with all FeatureSpec objects created

### Case 2: Load metadata with missing required fields
- Given: A metadata YAML file missing required fields (e.g., missing 'dim')
- When: FeatureProviderBase is initialized with this metadata path
- Then: Loading should handle the missing field gracefully (or raise appropriate error)

### Case 3: Load malformed YAML
- Given: A YAML file with invalid syntax (malformed structure)
- When: FeatureProviderBase is initialized with this metadata path
- Then: YAML parsing should raise appropriate error

### Case 4: Auto-validation detects missing method implementations
- Given: A metadata file declaring a feature "test_feature"
- When: FeatureProviderBase is initialized and the subclass does not implement get_test_feature()
- Then: Validation should fail with error message indicating method not found

### Case 5: Auto-validation detects dimension mismatch
- Given: A metadata file declaring feature dimension 3
- When: FeatureProviderBase is initialized and get_feature() returns array of dimension 2
- Then: Validation should fail with dimension mismatch error

### Case 6: Auto-validation detects method throwing exception
- Given: A metadata file declaring a feature
- When: FeatureProviderBase is initialized and get_feature() raises an exception
- Then: Validation should fail with error message indicating method call failed

### Case 7: Get all features concatenates correctly
- Given: FeatureProviderBase with multiple features in metadata
- When: get_all_features() is called
- Then: Returns concatenated numpy array with features in metadata order

### Case 8: Get feature by name (valid)
- Given: FeatureProviderBase with feature "test_feature" in metadata
- When: get_feature("test_feature") is called
- Then: Returns the correct feature vector

### Case 9: Get feature by name (not found)
- Given: FeatureProviderBase with feature "test_feature" in metadata
- When: get_feature("non_existent") is called
- Then: Raises ValueError with message indicating feature not found

### Case 10: Get feature dimension mismatch
- Given: FeatureProviderBase with feature dimension 3 in metadata
- When: get_feature() returns array of dimension 2
- Then: Raises ValueError with dimension mismatch message

## Status
- [x] Write scenario document
- [ ] Write solid test according to document
- [ ] Run test and watch it failing
- [ ] Implement to make test pass
- [ ] Run test and confirm it passed
- [ ] Refactor implementation without breaking test
- [ ] Run test and confirm still passing after refactor
