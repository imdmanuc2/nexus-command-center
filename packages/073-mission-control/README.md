# Package 073 — Mission Control

Version 1 UX milestone for Nexus Command Center.

## Purpose

Transform Home V2 from a large multi-purpose dashboard into a calm Mission Control landing experience that answers four questions quickly:

1. Is the platform healthy?
2. Is production running?
3. What needs attention?
4. Where should the operator go next?

## Changes

- Renames Home V2 presentation to **Nexus Mission Control**.
- Adds canonical top-level summary cards for health, hashrate, workers, pools, nodes, and critical alerts.
- Adds explicit CMDB / Operations / Explorer workflow links.
- Promotes Needs Attention, Operations Brief, Operational Readiness, and Recent Activity.
- Moves detailed forecast, MiningCore, pool, miner, node, trend, alert, and production widgets behind **Engineering & Production Detail** while preserving all existing widget IDs and live rendering.
- Adds Version 1 product principles documentation.
- Continues consuming `/api/platform/dashboard-summary`; no new dashboard data source is introduced.

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages
unzip -o 073-mission-control.zip
cd 073-mission-control/nexus
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
