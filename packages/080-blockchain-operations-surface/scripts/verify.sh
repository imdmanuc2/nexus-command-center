#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

echo "===== PACKAGE 080 VERIFY ====="

python3 -m py_compile \
  backend/services/blockchain_operations_service.py \
  backend/modules/blockchain_management.py \
  backend/api/server.py

echo "PASS: Python syntax"

grep -q 'label: "Blockchain"' frontend/js/nav.js
echo "PASS: Blockchain primary navigation entry"

grep -q '"/api/blockchain/operations"' backend/api/server.py
echo "PASS: native blockchain operations API route"

grep -q 'def operations(' backend/modules/blockchain_management.py
echo "PASS: blockchain management API adapter"

grep -q '"/blockchain.html"' backend/api/server.py
echo "PASS: blockchain static page route"

test -f frontend/blockchain.html
test -f frontend/js/blockchain.js
test -f frontend/css/blockchain.css

echo "PASS: blockchain frontend files"

python3 - <<'PYVERIFY'
from backend.services.blockchain_operations_service import (
    get_blockchain_operations,
)

payload = get_blockchain_operations()

assert payload["status"] == "ok"
assert payload["source"] == "nexus-postgresql-platform"
assert payload["count"] == 2

bch = next(
    item
    for item in payload["items"]
    if item.get("coin") == "BCH"
)

btc = next(
    item
    for item in payload["items"]
    if item.get("coin") == "BTC"
)

print()
print("BCH")
print(bch)

assert bch["state"] == "syncing"
assert bch["rpcReachable"] is True
assert bch["rpcHealthy"] is True
assert bch["syncProgress"] is not None
assert bch["peerCount"] is not None

print()
print("PASS: BCH projects as canonical syncing runtime")

print()
print("BTC")
print(btc)

assert btc["state"] in {
    "warning",
    "unknown",
    "offline",
    "syncing",
    "running",
}

print()
print("PASS: BTC state preserved without false healthy override")
PYVERIFY

echo
echo "PASS: Package 080 verification"
