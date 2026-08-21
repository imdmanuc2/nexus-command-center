#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "===== PACKAGE 081 DOCTOR ====="

python3 -m py_compile \
  backend/services/monero_runtime_preflight_service.py

echo "PASS: Python syntax"

test -f backend/data/private/managed_hosts.json
echo "PASS: managed host profile exists"

test -f backend/data/private/known_hosts
echo "PASS: managed host known_hosts exists"

test -f backend/data/config/blockchain_provider_catalog.json
echo "PASS: blockchain provider catalog exists"

python3 - <<'PY'
from backend.transports.target_resolver import resolve_target

target = resolve_target({
    "entityId": "asset-host-be24584e412bf6f6",
    "inputPayload": {"transport": "ssh"},
})

assert target.host
assert target.username
assert target.identity_file
assert target.known_hosts_file

print("PASS: canonical managed host resolves")
PY

echo "PACKAGE 081 DOCTOR PASS"
