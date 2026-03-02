# Scenario: Validation Uses Discovered Revision Metadata

- Given: A shared artifacts directory with a valid revision containing observations_metadata.yaml
- When: The system discovers the latest revision and loads metadata from it
- Then: Validation must use the metadata from the discovered revision, not repository-local fallback files

## Test Steps

- Case 1 (revision metadata): System loads metadata from discovered revision path via `discover_latest_revision()`
- Case 2 (fallback not used): Repository-local fallback file exists but is ignored in favor of discovered revision
- Case 3 (valid revision selected): Multiple revisions exist, metadata from the latest valid revision is used

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
