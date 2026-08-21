#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

PKG="packages/082-managed-blockchain-privileged-runtime-helper"

echo "===== PACKAGE 082 DOCTOR ====="

python3 -m py_compile \
  "$PKG/payload/seymour-blockchain-runtime"

echo "PASS: helper Python syntax"

grep -q \
  '^umbrel ALL=(root) NOPASSWD: /usr/local/libexec/seymour-blockchain-runtime \*$' \
  "$PKG/payload/nexus-seymour-blockchain-runtime"

echo "PASS: narrow sudoers contract"

if grep -Eq \
  'NOPASSWD:[[:space:]]*ALL|ALL=\(ALL(:ALL)?\)[[:space:]]*NOPASSWD:[[:space:]]*ALL' \
  "$PKG/payload/nexus-seymour-blockchain-runtime"
then
    echo "ERROR: unrestricted sudo detected"
    exit 1
fi

echo "PASS: unrestricted sudo prohibited"

python3 - <<'PY'
from backend.transports.target_resolver import resolve_target

target = resolve_target({
    "entityId": "asset-host-be24584e412bf6f6",
    "inputPayload": {
        "transport": "ssh",
    },
})

assert target.host == "192.168.1.154"
assert target.username == "umbrel"

print("PASS: canonical managed runtime host resolves")
PY

echo "PACKAGE 082 DOCTOR PASS"
