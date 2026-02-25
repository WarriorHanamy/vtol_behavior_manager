# Step 1 - Understand Intent

## Functional Requirements

### FR-1: FeatureSpec Dataclass
Create a dataclass `FeatureSpec` with fields:
- `name` (str): Feature name
- `dim` (int): Feature dimension
- `dtype` (str): Data type (e.g., "float32", "float64")
- `description` (str): Human-readable description

### FR-2: FeatureValidationResult Dataclass
Create a dataclass `FeatureValidationResult` for validation reporting with fields to track:
- Feature name
- Validation status (pass/fail)
- Error message if any
- Expected dimension vs actual dimension

### FR-3: Metadata Loading
Implement `_load_metadata()` method in `FeatureProviderBase` that:
- Parses `observation_metadata.yaml` file
- Extracts feature specifications (name, dim, dtype, description)
- Returns a list of `FeatureSpec` objects

### FR-4: Convention-Based Discovery
Implement `_validate_implementations()` method that:
- Discovers feature implementations using naming convention `get_{feature_name}`
- Validates each feature exists as a method in the provider
- Checks that implementation output dimension matches metadata specification
- Returns validation results for all features

### FR-5: Validation Reporting
Implement `_print_validation_report()` method that:
- Prints clear pass/fail indicators for each feature
- Shows validation status at initialization
- Uses print statements for output

### FR-6: Get All Features
Implement `get_all_features()` method that:
- Concatenates all features in the order specified in metadata
- Returns a numpy array combining all feature vectors

### FR-7: Get Single Feature
Implement `get_feature()` method that:
- Retrieves a single feature by name
- Performs error checking (valid feature name, dimension check)
- Returns the feature vector

### FR-8: Programmatic Validation Report
Implement `get_validation_report()` method that:
- Provides programmatic access to validation results
- Returns validation results data structure
- Allows testing of validation status

## Assumptions

### Assumption 1: observation_metadata.yaml Structure
The `observation_metadata.yaml` file structure is not explicitly defined in the task. Based on the task description mentioning "name, dim, dtype, description fields", I assume the structure is:

```yaml
features:
  - name: target_error
    dim: 3
    dtype: float32
    description: "Position error vector in FLU body frame"
  - name: gravity_projection
    dim: 3
    dtype: float32
    description: "Gravity vector in FLU body frame"
  # ... more features
```

### Assumption 2: FeatureProviderBase Location
The task specifies "in vtol-interface/src/features/", so I assume:
- Directory: `/home/rec/server/vtol-interface/src/features/`
- Files: `__init__.py` and `feature_provider_base.py`

### Assumption 3: Naming Convention
The task mentions "convention-based feature discovery (get_{feature_name})", so I assume:
- Each feature is implemented as a method named `get_{feature_name}` in subclasses
- Example: feature `target_error` has method `get_target_error()`
- Example: feature `gravity_projection` has method `get_gravity_projection()`

### Assumption 4: observation_metadata.yaml Location
The task mentions parsing `observation_metadata.yaml`. I assume:
- It's located in a configurable path (passed to constructor or environment variable)
- Default location could be relative to the features directory or specified by caller

### Assumption 5: Validation at Initialization
The task says "reports clear validation status at initialization", so I assume:
- Validation happens in `__init__` or a separate initialization method
- Validation report is printed automatically during initialization

### Assumption 6: Testing Infrastructure
Based on existing code structure, I assume:
- Tests go in `vtol-interface/tests/scenario/` or similar
- Tests use pytest framework
- Tests follow the pattern from previous feature registry loader tests
