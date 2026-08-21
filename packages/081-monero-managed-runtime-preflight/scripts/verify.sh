#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "===== PACKAGE 081 VERIFY ====="

python3 -m py_compile \
  backend/services/monero_runtime_preflight_service.py

python3 - <<'PY'
import json

from backend.services.monero_runtime_preflight_service import preflight

payload = preflight()

print(json.dumps(payload, indent=2, default=str))

assert payload["providerId"] == "monero-mainnet"
assert payload["host"]["assetId"] == "asset-host-be24584e412bf6f6"
assert payload["storage"]["path"] == "/mnt/seymour-storage/monero-mainnet"

for key in (
    "hostResolved",
    "sshReachable",
    "architectureSupported",
    "dockerInstalled",
    "dockerSocketPresent",
    "dockerDaemonAccessible",
    "privilegedExecutionAvailable",
    "storagePresent",
    "storageWritable",
    "capacitySufficient",
    "p2pPortAvailable",
    "rpcPortAvailable",
    "runtimeInventoryAvailable",
    "runtimeAbsent",
):
    assert key in payload["checks"]

assert payload["checks"]["dockerInstalled"] is True
assert payload["checks"]["dockerSocketPresent"] is True

# Package 081 must report privilege limitations rather than weakening
# the managed host security model.
if not payload["checks"]["dockerDaemonAccessible"]:
    assert payload["ready"] is False
    assert "dockerDaemonAccessible" in payload["blockers"]

if not payload["checks"]["privilegedExecutionAvailable"]:
    assert payload["ready"] is False
    assert "privilegedExecutionAvailable" in payload["blockers"]

print()
print("PASS: Monero preflight contract")
PY

echo "PACKAGE 081 VERIFY PASS"
