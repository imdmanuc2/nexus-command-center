# 033 — Home V2 Operational Readiness

Beta-hardens the existing Home V2 dashboard without redesigning it.

## Changes

- Adds an 8-second timeout to canonical Platform API requests.
- Detects stale and critically stale fleet telemetry.
- Preserves the last successful dashboard data during transient API failures.
- Escalates repeated refresh failures from `STALE DATA` to `DATA OFFLINE`.
- Refreshes immediately when the browser tab becomes visible or networking returns.
- Shows an explicit browser-offline state.
- Uses the same guarded JSON request path for the PostgreSQL-backed Platform Timeline.

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages
unzip 033-home-v2-operational-readiness.zip
cd 033-home-v2-operational-readiness
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
