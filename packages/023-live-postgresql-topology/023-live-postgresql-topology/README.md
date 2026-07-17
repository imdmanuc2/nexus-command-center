
# Package 023 — Live PostgreSQL Topology

Makes PostgreSQL the authoritative source for Infrastructure Explorer nodes and
relationships.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## Topology model

- Current matched worker session becomes live state on its physical asset.
- Physical asset points directly to its current pool with `mines-on`.
- Pool points to the matching blockchain asset with `backed-by`.
- Historical, unknown, stale, and offline worker sessions are excluded.
- The frontend no longer derives asset-to-pool edges in JavaScript.
