# Changelog

## Package 029
- Added persistent live operation sessions and structured events.
- Added progress and verification lifecycle emission.
- Added operation session APIs.
- Added Operations Center live console drawer and timeline.
- Added Migration 020 and install/doctor/verify/rollback scripts.

## 029.1

- Removed the unsupported dependency on `nexus.schema_migrations`.
- Kept Migration 020 idempotent.
- Verification now checks the actual operation-session tables and indexes.
