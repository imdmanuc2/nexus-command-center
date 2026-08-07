# Package 057 — CMDB Object Model & Relationship Engine

This is the real implementation package built against the current Nexus Command Center repository.

## Delivers

- Canonical PostgreSQL-backed CMDB object registry
- Friendly-name resolution for relationship endpoints
- Canonical object API and detail API
- Canonical CMDB object page
- Clickable pool, node, workload, and relationship records
- Breadcrumb navigation and relationship traversal
- Backup-aware installation and rollback

## Routes

- `GET /api/platform/objects`
- `GET /api/platform/objects/{object_type}/{object_id}`
- `GET /cmdb-object.html?type={object_type}&id={object_id}`

## Install

Run from `057-cmdb-object-model-relationship-engine/nexus`:

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
