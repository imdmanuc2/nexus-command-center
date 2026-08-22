#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "===== PACKAGE 083 DOCTOR ====="

python3 -m py_compile \
  backend/services/monero_runtime_install_service.py

echo "PASS: Python syntax"

python3 - <<'PY'
from backend.services.monero_runtime_preflight_service import preflight

payload = preflight()

assert payload["ready"] is True
assert payload["status"] == "ready"
assert payload["blockers"] == []

print("PASS: Package 081 readiness gate")
PY

python3 - <<'PY'
from backend.services.monero_runtime_install_service import plan

payload = plan()

print("adapter =", payload["installAdapter"]["path"])
print("nativeState =", payload["nativeState"])
print("runtimeMatches =", len(payload["runtimeMatches"]))
print("blockers =", payload["blockers"])

assert payload["installAdapter"]["available"] is True

print("PASS: native Monero installation adapter discovered")
PY

echo "PACKAGE 083 DOCTOR PASS"
