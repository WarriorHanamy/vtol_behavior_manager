# Scenario: Optional Model Integrity Verification
- Given: A loaded model with metadata that may or may not contain checksum
- When: _verify_checksum() is called
- Then: It verifies the MD5 checksum if available, optionally raises error on mismatch

## Test Steps

- Case 1 (checksum matches): Metadata contains checksum, model file checksum matches, passes
- Case 2 (checksum mismatch): Metadata contains checksum, model file checksum differs, raises error
- Case 3 (no checksum): Metadata doesn't contain checksum, verification skipped gracefully
- Case 4 (invalid checksum): Metadata has invalid checksum format, handled gracefully
- Case 5 (file changed): Model file modified after export, checksum mismatch detected

## Status
- [x] Write scenario document
- [x] Write solid test according to document
- [x] Run test and watch it failing
- [x] Implement to make test pass
- [x] Run test and confirm it passed
- [x] Refactor implementation without breaking test
- [x] Run test and confirm still passing after refactor
