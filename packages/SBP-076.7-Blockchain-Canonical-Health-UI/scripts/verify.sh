#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." &&
  pwd
)"

cd "$ROOT"

echo "===== SBP-076.7 VERIFY ====="

grep -q 'id="topNav"' \
  frontend/blockchain.html

echo "PASS: shared Nexus navigation target"

grep -q '>Ready<' \
  frontend/blockchain.html

grep -q 'blockchainReadyCount' \
  frontend/blockchain.html

echo "PASS: canonical summary semantics"

for field in \
  overallState \
  runtimeState \
  connectivityState \
  syncState \
  rpcState \
  miningReadiness \
  syncProgress
do
  grep -q "$field" frontend/js/blockchain.js
  echo "PASS: UI consumes $field"
done

grep -q \
  '"/api/blockchain/catalog"' \
  frontend/js/blockchain.js

grep -q \
  'Available Blockchains' \
  frontend/blockchain.html

echo "PASS: provider catalog preserved"

python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8080/api/blockchain/operations",
    timeout=5,
) as response:
    payload=json.load(response)

items=payload.get("items") or []

assert len(items) >= 4, payload

ready=sum(
    1
    for item in items
    if item.get("overallState") == "ready"
)

syncing=sum(
    1
    for item in items
    if item.get("overallState") == "syncing"
)

attention=sum(
    1
    for item in items
    if item.get("overallState")
    not in {"ready", "running", "syncing"}
)

print("runtimes =", len(items))
print("ready =", ready)
print("syncing =", syncing)
print("attention =", attention)

for item in items:
    print()
    print(
        item.get("coin"),
        "—",
        item.get("name"),
    )
    print(
        "  overallState =",
        item.get("overallState"),
    )
    print(
        "  runtimeState =",
        item.get("runtimeState"),
    )
    print(
        "  connectivityState =",
        item.get("connectivityState"),
    )
    print(
        "  syncState =",
        item.get("syncState"),
    )
    print(
        "  rpcState =",
        item.get("rpcState"),
    )
    print(
        "  miningReadiness =",
        item.get("miningReadiness"),
    )
    print(
        "  syncProgress =",
        item.get("syncProgress"),
    )

assert ready >= 1
assert syncing >= 3
assert attention == 0

managed_syncing=[
    item
    for item in items
    if item.get("manager")
    and item.get("overallState") == "syncing"
]

assert len(managed_syncing) >= 3

for item in managed_syncing:
    progress=item.get("syncProgress")

    assert progress is not None, item
    assert 0 <= float(progress) <= 100, item

print()
print(
    "PASS: canonical live health supports "
    "Blockchain UI presentation"
)
PY

echo
echo "===== PAGE GET ====="

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

HTTP_CODE="$(
  curl -sS \
    -o "$TMP" \
    -w '%{http_code}' \
    http://127.0.0.1:8080/blockchain.html
)"

test "$HTTP_CODE" = "200"

grep -q \
  '<title>Blockchain | Nexus Command Center</title>' \
  "$TMP"

echo "PASS: Blockchain page HTTP GET"

echo
echo "SBP-076.7 VERIFY PASS"
