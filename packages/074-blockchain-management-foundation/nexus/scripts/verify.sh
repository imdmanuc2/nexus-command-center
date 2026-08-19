#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

echo "Package 074 verify: Blockchain Management Foundation"

/usr/bin/python3 - <<'PY'
from backend.services.blockchain_management_service import (
    catalog,
    create_deployment_plan,
)

result = catalog()

assert result["status"] == "ok"
assert result["count"] >= 3

ids = {
    provider["providerId"]
    for provider in result["providers"]
}

assert "bitcoin-mainnet" in ids
assert "bitcoin-cash-mainnet" in ids
assert "monero-mainnet" in ids

print("PASS: blockchain provider catalog")

plan = create_deployment_plan({
    "providerId": "monero-mainnet",
    "hostAssetId": "verification-host",
    "storage": {
        "selectionMode": "custom",
        "path": "/srv/blockchains",
    },
    "network": {
        "p2pPort": 18080,
        "rpcPort": 18081,
    },
})

assert plan["provider"]["coin"] == "XMR"
assert plan["hostAssetId"] == "verification-host"
assert plan["storage"]["selectionMode"] == "custom"
assert plan["storage"]["customPath"] == "/srv/blockchains"
assert plan["network"]["p2pPort"] == 18080
assert plan["network"]["rpcPort"] == 18081
assert plan["executable"] is False

print("PASS: deployment planning contract")

plan = create_deployment_plan({
    "providerId": "bitcoin-mainnet",
    "hostAssetId": "verification-host",
    "storage": {
        "selectionMode": "discovered",
        "targetId": "disk-1",
    },
})

assert plan["network"]["p2pPort"] == 8333
assert plan["network"]["rpcPort"] == 8332
assert plan["storage"]["targetId"] == "disk-1"

print("PASS: discovered storage contract")
print("PASS: execution prohibited")
PY

if grep -R \
  -E '192\.168\.1\.|/home/umbrel|/mnt/seymour-storage' \
  backend/data/config/blockchain_provider_catalog.json
then
  echo "FAIL: customer-specific path or address in provider catalog"
  exit 1
fi

echo "PASS: provider catalog contains no Seymour-local infrastructure"

echo "Package 074 verify: PASS"

grep -q \
  '"/api/blockchain/catalog": blockchain_management.catalog' \
  backend/api/server.py

grep -q \
  'if self.path == "/api/blockchain/deployment-plan":' \
  backend/api/server.py

echo "PASS: Blockchain Management API route contract"

grep -q 'CMDB_CANONICAL_SOURCE = True' \
  backend/services/blockchain_management_service.py

grep -q 'CMDB is the canonical source of truth' \
  packages/074-blockchain-management-foundation/README.md

echo "PASS: CMDB canonical source-of-truth contract"
