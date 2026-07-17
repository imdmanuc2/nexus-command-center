#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

python3 -m scripts.sync_platform_inventory

echo
echo "== Platform inventory =="
curl -fsS http://127.0.0.1:8080/api/platform/inventory   | jq '{status, source, counts}'

echo
echo "== Workers =="
curl -fsS http://127.0.0.1:8080/api/platform/inventory   | jq '.workers[] | {
      workerId,
      workerType,
      hardwareType,
      displayName,
      assetId,
      assetMatched,
      poolInstanceId,
      nativePoolId,
      status
    }'

echo
echo "== Topology counts =="
curl -fsS http://127.0.0.1:8080/api/platform/topology   | jq '{
      pools: (.nodes.pools | length),
      workers: (.nodes.workers | length),
      workloads: (.nodes.workloads | length),
      relationships: (.relationships | length)
    }'
