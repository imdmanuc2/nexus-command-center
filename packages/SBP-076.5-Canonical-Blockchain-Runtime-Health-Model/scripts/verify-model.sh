#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

MODEL="packages/SBP-076.5-Canonical-Blockchain-Runtime-Health-Model/payload/backend/services/blockchain_runtime_health_service.py"

echo "===== SBP-076.5 MODEL VERIFY ====="

python3 - "$MODEL" <<'PY'
from pathlib import Path
import sys

namespace = {}

path = Path(sys.argv[1])

exec(
    compile(
        path.read_text(),
        str(path),
        "exec",
    ),
    namespace,
)

derive = namespace[
    "derive_blockchain_runtime_health"
]


def check(name, observation, expected):
    result = derive(observation)

    print()
    print("-----", name, "-----")

    for key in (
        "runtimeState",
        "connectivityState",
        "syncState",
        "rpcState",
        "miningReadiness",
        "overallState",
        "syncProgress",
    ):
        print(
            key,
            "=",
            result.get(key),
        )

    for key, wanted in expected.items():
        actual = result.get(key)

        assert actual == wanted, (
            name,
            key,
            actual,
            wanted,
        )


check(
    "BCH syncing",
    {
        "running": True,
        "rpcReachable": True,
        "rpcHealthy": True,
        "initialBlockDownload": True,
        "syncProgress": 11.02,
    },
    {
        "runtimeState": "running",
        "connectivityState": "online",
        "syncState": "syncing",
        "rpcState": "healthy",
        "miningReadiness": "not-ready",
        "overallState": "syncing",
    },
)

check(
    "BCH stalled",
    {
        "running": True,
        "rpcReachable": True,
        "rpcHealthy": True,
        "initialBlockDownload": True,
        "syncProgress": 11.02,
        "syncStalled": True,
    },
    {
        "runtimeState": "running",
        "connectivityState": "online",
        "syncState": "stalled",
        "rpcState": "healthy",
        "miningReadiness": "not-ready",
        "overallState": "stalled",
    },
)

check(
    "Native Bitcoin fully synced",
    {
        "nodeStatus": "online",
        "rpcConnected": True,
        "syncProgress": 99.999995,
        "blockHeight": 963868,
        "headerHeight": 963868,
    },
    {
        "runtimeState": "running",
        "connectivityState": "online",
        "syncState": "synced",
        "rpcState": "healthy",
        "miningReadiness": "ready",
        "overallState": "ready",
    },
)

check(
    "Managed Bitcoin lifecycle only",
    {
        "running": True,
    },
    {
        "runtimeState": "running",
        "connectivityState": "unknown",
        "syncState": "unknown",
        "rpcState": "unknown",
        "miningReadiness": "unknown",
        "overallState": "running",
    },
)

check(
    "Managed Monero lifecycle only",
    {
        "running": True,
    },
    {
        "runtimeState": "running",
        "connectivityState": "unknown",
        "syncState": "unknown",
        "rpcState": "unknown",
        "miningReadiness": "unknown",
        "overallState": "running",
    },
)

check(
    "Stopped runtime",
    {
        "running": False,
    },
    {
        "runtimeState": "stopped",
        "syncState": "unknown",
        "miningReadiness": "not-ready",
        "overallState": "stopped",
    },
)

check(
    "RPC unreachable",
    {
        "running": True,
        "rpcReachable": False,
    },
    {
        "runtimeState": "running",
        "connectivityState": "unreachable",
        "rpcState": "unreachable",
        "miningReadiness": "not-ready",
        "overallState": "offline",
    },
)

print()
print("PASS: canonical blockchain health-model behavior")
PY

echo
echo "SBP-076.5 MODEL VERIFY PASS"
