# Package 032 — Home V2 Beta Integration

This package completes the first beta-focused frontend cleanup for Home V2.

## Scope

- Replaces the legacy JSON-backed `/api/events/operations` activity feed call.
- Uses the canonical PostgreSQL-backed `/api/platform/timeline/latest` endpoint.
- Normalizes timeline entries into the existing Home V2 activity-feed model.
- Preserves the existing Home V2 layout and visual design.
- Adds package verification for the canonical endpoint and JavaScript syntax.

## Install

Run from the Nexus Command Center repository root:

```bash
unzip package-032-home-v2-beta-integration.zip -d packages/
cd packages/package-032-home-v2-beta-integration
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
