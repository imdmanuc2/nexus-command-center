# Package 032 — Maintenance Windows

Adds platform-wide planned-maintenance scheduling for individual assets and flexible target selectors: asset type, site, rack, pool, cluster, and tag.

## Capabilities

- PostgreSQL maintenance window and target model
- Scheduled, active, completed, and cancelled effective states
- REST API for listing, creating, cancelling, and checking entity status
- Alert suppression for active matching windows
- Immutable audit events for create/cancel actions
- Initial Maintenance Windows UI
- Targets support miners, pools, nodes, hosts, VMs, racks, sites, clusters, and tagged collections

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages
unzip 032-maintenance-windows.zip
cd 032-maintenance-windows
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## API

- `GET /api/platform/maintenance/windows`
- `GET /api/platform/maintenance/window?windowId=...`
- `GET /api/platform/maintenance/status?entityType=worker&entityId=...`
- `POST /api/platform/maintenance/create`
- `POST /api/platform/maintenance/cancel`

The target selector is intentionally generic so future bulk operations can schedule maintenance for entire racks, sites, pools, clusters, or tagged collections without redesigning the schema.
