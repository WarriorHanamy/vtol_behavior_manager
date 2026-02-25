# Scenario: List Available Models
- Given: A ModelDiscoverer instance with configured search paths
- When: list_available_models() is called
- Then: It scans all search paths and returns a list of available models with their locations

## Test Steps

- Case 1 (multiple models): Multiple models found in different search paths, all listed
- Case 2 (no models): No models found in any search path, returns empty list
- Case 3 (single model): Single model found, returns list with one entry
- Case 4 (duplicate names): Models with same name in different paths, first found listed
- Case 5 (partial metadata): Some metadata files are malformed, valid ones still listed

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
