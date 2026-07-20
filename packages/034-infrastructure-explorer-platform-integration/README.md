# Package 034 — Infrastructure Explorer Platform Integration

Completes the Infrastructure Explorer data-path migration for the Nexus Version 1 beta.

## Changes

- Loads topology directly from `/api/platform/topology`.
- Loads reconciled workers directly from `/api/platform/workers`.
- Removes global `window.fetch` interception from the Explorer adapter.
- Preserves last-known-good worker telemetry during transient worker API failures.
- Adds an eight-second timeout to Platform Explorer requests.
- Keeps the existing rebuild control as a reconciliation action, while rendering only canonical Platform topology afterward.
- Shows `Live · Platform` when the Explorer is successfully backed by PostgreSQL Platform data.
- Preserves the existing canvas, Digital Twin drawer, Overview/Engineering modes, relationship activity logic, and layout behavior.

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages
unzip 034-infrastructure-explorer-platform-integration.zip
cd 034-infrastructure-explorer-platform-integration
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
