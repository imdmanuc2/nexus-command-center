# Package 027 — Managed Executors

Introduces the reusable Nexus managed-executor framework and the first real
read-only Bitcoin Core executor.

## Included executors

- Bitcoin: live RPC test, synchronization check, wallet verification, and
  diagnostics collection.
- MiningCore, Linux, and ASIC: registered placeholders that return safe,
  audited no-op results until their managed transports are enabled.

## Safety

- Package 026 queue, approval, and audit controls remain authoritative.
- Dry-run remains the default in Operations Center.
- Bitcoin actions are read-only.
- No SSH commands, service restarts, or host mutations are enabled here.
- Unknown actions remain safe no-ops.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## Live Bitcoin action request example

```bash
curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "actionId":"bitcoin.check-sync",
    "entityType":"blockchain-node",
    "entityId":"YOUR-BITCOIN-ASSET-ID",
    "requestedBy":"operator",
    "dryRun":false,
    "inputPayload":{"coin":"BTC"}
  }' \
  http://127.0.0.1:8080/api/platform/automation/request

curl -X POST \
  -H 'Content-Type: application/json' \
  -d '{"limit":25}' \
  http://127.0.0.1:8080/api/platform/automation/process
```
