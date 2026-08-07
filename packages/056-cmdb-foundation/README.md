# Package 056 — CMDB Foundation

Establishes the Nexus CMDB as the operator-facing source-of-truth workspace.

## Changes

- Renames Assets to CMDB in the shared navigation and page branding.
- Preserves `/assets.html` for Version 1.0 compatibility.
- Adds CMDB sections for Overview, Assets, Pools, Blockchain Nodes, Services, Workloads, Relationships, Discovery, and Audit.
- Prefers `/api/platform/inventory` as the authoritative asset source, with discovery only as an explicit fallback.
- Loads platform pools, workers, workloads, relationships, topology, and CMDB audit data.
- Preserves the existing asset search, filters, lifecycle controls, dependency mapping, intelligence, and drawer.

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages/056-cmdb-foundation/nexus
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
