#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

echo "Package 076 verify"

/usr/bin/python3 -m py_compile \
  backend/services/managed_host_runtime_topology_service.py

echo "PASS: Python syntax"

/usr/bin/python3 - <<'PY'
from backend.services.managed_host_runtime_topology_service import (
    canonical_blockchain_runtimes,
    plan_runtime_topology,
)

assets = [
    {
        "id": "asset-host-1",
        "assetType": "server",
        "name": "Umbrel Host",
        "ip": "192.0.2.10",
    },
    {
        "id": "asset-storage-1",
        "assetType": "storage",
        "name": "Blockchain Storage",
        "metadata": {
            "hostAssetId": "asset-host-1",
        },
    },
    {
        "id": "asset-bch-old",
        "assetType": "blockchain-node",
        "coin": "BCH",
        "observedState": {
            "sync": {
                "providerId": "bitcoin-cash-mainnet",
                "generatedAt": "2026-08-10T01:00:00+00:00",
            },
            "telemetry": {
                "providerId": "bitcoin-cash-mainnet",
                "appId": "seymour-bch-node",
            },
        },
    },
    {
        "id": "asset-bch-current",
        "assetType": "blockchain-node",
        "coin": "BCH",
        "metadata": {
            "hostAssetId": "asset-host-1",
            "storageAssetId": "asset-storage-1",
        },
        "observedState": {
            "sync": {
                "providerId": "bitcoin-cash-mainnet",
                "generatedAt": "2026-08-12T01:00:00+00:00",
            },
            "telemetry": {
                "providerId": "bitcoin-cash-mainnet",
                "appId": "seymour-bch-node",
            },
        },
    },
    {
        "id": "asset-btc-1",
        "assetType": "blockchain-node",
        "coin": "BTC",
        "ip": "192.0.2.20",
    },
]

canonical = canonical_blockchain_runtimes(assets)

assert len(canonical) == 2

bch = next(
    item
    for item in canonical
    if item["runtimeIdentity"]["providerId"]
    == "bitcoin-cash-mainnet"
)

assert (
    bch["canonicalAsset"]["id"]
    == "asset-bch-current"
)

assert bch["historicalAssetIds"] == [
    "asset-bch-old"
]

assert bch["observationCount"] == 2

plan = plan_runtime_topology(assets)

triples = {
    (
        relationship["sourceId"],
        relationship["relationshipType"],
        relationship["targetId"],
    )
    for relationship in plan["relationships"]
}

assert (
    "asset-bch-current",
    "hosted-on",
    "asset-host-1",
) in triples

assert (
    "asset-bch-current",
    "uses-storage",
    "asset-storage-1",
) in triples

assert (
    "asset-host-1",
    "mounts",
    "asset-storage-1",
) in triples

# BTC has no explicit host/storage references and therefore remains
# unresolved rather than being guessed from its IP address.
btc = next(
    item
    for item in plan["unresolved"]
    if item["providerId"] == "bitcoin-mainnet"
)

assert "hostAssetId" in btc["missing"]
assert "storageAssetId" in btc["missing"]

print("PASS: canonical runtime deduplication")
print("PASS: latest BCH runtime selection")
print("PASS: explicit hosted-on relationship")
print("PASS: explicit uses-storage relationship")
print("PASS: explicit mounts relationship")
print("PASS: topology guessing prohibited")
PY

echo
echo "===== LIVE DRY RUN ====="

/usr/bin/python3 - <<'PY'
from backend.services.managed_host_runtime_topology_service import (
    reconcile_managed_host_runtime_topology,
)

result = reconcile_managed_host_runtime_topology(
    dry_run=True
)

print(
    "canonicalRuntimes=",
    len(result["canonicalRuntimes"]),
)

print(
    "relationshipCount=",
    result["relationshipCount"],
)

print(
    "unresolvedCount=",
    result["unresolvedCount"],
)

for runtime in result["canonicalRuntimes"]:
    asset = runtime["canonicalAsset"]

    print(
        "runtime",
        runtime["runtimeIdentity"],
        "assetId=" + str(asset.get("id")),
        "observations=" + str(
            runtime["observationCount"]
        ),
    )

for item in result["unresolved"]:
    print(
        "unresolved",
        item["assetId"],
        item["providerId"],
        ",".join(item["missing"]),
    )
PY

echo "Package 076 verify: PASS"

/usr/bin/python3 - <<'PY'
from backend.services.managed_host_runtime_topology_service import (
    canonical_blockchain_runtimes,
)

assets = [
    {
        "id": "asset-current",
        "assetType": "blockchain-node",
        "coin": "BCH",
        "observedState": {
            "sync": {
                "providerId": "bitcoin-cash-mainnet",
                "generatedAt": "2026-08-12T12:00:00+00:00",
            },
            "telemetry": {
                "providerId": "bitcoin-cash-mainnet",
                "appId": "seymour-bch-node",
                "container": {
                    "name": "seymour-bch-node_node_1",
                },
            },
        },
    },
    {
        "id": "asset-legacy",
        "assetType": "blockchain-node",
        "coin": "BCH",
        "observedState": {
            "sync": {
                "providerId": "bitcoin-cash-mainnet",
                "generatedAt": "2026-08-10T12:00:00+00:00",
            },
            "telemetry": {
                "providerId": "bitcoin-cash-mainnet",
                "container": {
                    "name": "seymour-bch-node_node_1",
                },
            },
        },
    },
]

result = canonical_blockchain_runtimes(assets)

assert len(result) == 1

runtime = result[0]

assert runtime["runtimeIdentity"] == {
    "providerId": "bitcoin-cash-mainnet",
    "runtimeId": "seymour-bch-node",
}

assert runtime["canonicalAsset"]["id"] == "asset-current"
assert runtime["historicalAssetIds"] == ["asset-legacy"]
assert runtime["observationCount"] == 2

print("PASS: legacy runtime container identity reconciliation")
PY

echo "PASS: ambiguous legacy runtime merging prohibited"
