# Package 048 — Verification Framework & Evidence Engine (R2)

Reusable, database-backed verification for Nexus operations.

## Nexus-native integration

- Uses the existing `ThreadingHTTPServer` and `NexusHandler` route-dispatch pattern.
- Uses `/usr/bin/python3`, matching the Nexus API and worker services.
- Installs an idempotent route patch with explicit Package 048 markers.
- Installs a systemd worker using the repository path and current operating-system user.
- Does not require FastAPI or a Python virtual environment.

## Includes

- Verification profiles and ordered steps
- Durable queued runs and lease-based worker
- Step evidence and immutable events
- Capability, TCP, HTTP, file, and regex verifiers
- Change-request pass/fail integration
- Rollback recommendations
- Stale lease recovery
- REST API, systemd service, doctor/install/verify/rollback scripts

Run `scripts/doctor.sh`, `scripts/install.sh`, then `scripts/verify.sh`.
Commit only after verification passes.
