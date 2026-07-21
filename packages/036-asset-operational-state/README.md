# Package 036 — Asset Operational State

Adds platform-wide operational intent for every CMDB asset, including miners, pools, nodes, hosts, VMs, and future assets.

States: `active`, `maintenance`, `disabled`, `provisioning`, `decommissioning`, and `retired`.

The package keeps lifecycle status separate, records immutable state history, audits changes, supports bulk updates, and combines stored state with active Maintenance Windows to calculate an effective state. Alerts and recommendations can call the shared suppression helper instead of treating intentionally offline assets as failures.

## API

- `GET /api/platform/operational-state/summary`
- `GET /api/platform/operational-state/assets`
- `GET /api/platform/operational-state/asset?assetId=...`
- `GET /api/platform/operational-state/history?assetId=...`
- `POST /api/platform/operational-state/set`
- `POST /api/platform/operational-state/bulk-set`
- UI: `/operational-state.html`

## Install

Run `scripts/doctor.sh`, `scripts/install.sh`, then `scripts/verify.sh`.
