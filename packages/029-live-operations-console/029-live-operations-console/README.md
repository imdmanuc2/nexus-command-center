# Package 029 — Live Operations Console

Adds persistent operation sessions, structured timeline events, progress stages, and a reusable live console drawer to the Nexus Operations Center.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

The console opens when an automation run is clicked. It polls structured PostgreSQL events while the run is active and stops automatically at a terminal state.

## Event lifecycle

Queued → Connecting → Authorization → Executing → Verifying → Completed/Failed

Migration 020 creates `nexus.operation_sessions` and `nexus.operation_session_events`.
