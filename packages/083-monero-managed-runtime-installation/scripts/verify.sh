#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "===== PACKAGE 083 VERIFY ====="

python3 -m py_compile \
  backend/services/monero_runtime_install_service.py

echo "PASS: Python syntax"

python3 - <<'PY'
import json

from backend.services.monero_runtime_install_service import plan

payload = plan()

print(json.dumps(payload, indent=2, default=str))

assert payload["mode"] == "plan"
assert payload["writeOperations"] is False

assert payload["providerId"] == "monero-mainnet"
assert payload["appId"] == "seymour-monero-node"

assert payload["preflight"]["ready"] is True
assert payload["installAdapter"]["available"] is True

assert payload["runtimeInventoryAvailable"] is True
assert payload["runtimeMatches"] == []

assert payload["nativeState"] == "not-installed"

assert payload["ready"] is True
assert payload["blockers"] == []

assert (
    payload["confirmationRequired"]
    == "INSTALL-SEYMOUR-MONERO"
)

print()
print("PASS: Monero managed installation plan")
print("PASS: verification performed no runtime writes")
PY

echo
echo "===== EXECUTION GUARD ====="

python3 - <<'PY'
from backend.services.monero_runtime_install_service import execute

try:
    execute("")
except ValueError as exc:
    print(str(exc))
else:
    raise SystemExit(
        "ERROR: execution accepted without confirmation"
    )

print("PASS: explicit confirmation required")
PY

echo
echo "PACKAGE 083 VERIFY PASS"
