
# Package 024 — Operations Center Platform

Creates the unified PostgreSQL-backed operational view for the Operations
Center UI.

## Install

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## APIs

```text
GET /api/platform/operations-center
GET /api/platform/operations-center/status
GET /api/platform/operations-center/queue
GET /api/platform/operations-center/snapshot
```

The dashboard combines Fleet, Topology, Alerts, Recommendations, Automation,
and Timeline into one shared operational model.
