#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/Projects/Seymour/nexus-command-center"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for f in \
  backend/db/repositories/worker_repository.py \
  backend/jobs/platform_sync_job.py \
  backend/services/topology_service.py \
  frontend/js/graph.js; do
  test -f "$ROOT/$f" && echo "PASS: $f"
done
for f in \
  payload/backend/db/repositories/worker_repository.py \
  payload/backend/services/operational_state_engine.py \
  payload/backend/jobs/platform_sync_job.py; do
  test -f "$PKG/$f" && echo "PASS: $f"
done
curl -fsS --max-time 5 'http://192.168.1.169:8561/api/v1/statistics/workers?window=5m' >/dev/null
echo 'PASS: Seymour telemetry reachable'
python3 -m py_compile \
  "$PKG/payload/backend/db/repositories/worker_repository.py" \
  "$PKG/payload/backend/services/operational_state_engine.py" \
  "$PKG/payload/backend/jobs/platform_sync_job.py"
echo 'Doctor PASS'
