#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"
for file in \
  backend/services/seymour_pool_sync_service.py \
  backend/db/repositories/worker_repository.py \
  backend/services/operational_state_engine.py \
  frontend/js/graph.js
do
  [[ -f "$file" ]] && echo "PASS: $file" || { echo "FAIL: $file"; exit 1; }
done
curl -fsS 'http://192.168.1.169:8561/api/v1/statistics/workers?window=5m' >/dev/null
echo "PASS: Seymour telemetry reachable"
echo "Doctor PASS"
