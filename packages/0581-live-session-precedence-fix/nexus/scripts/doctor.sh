#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
cd "$REPO"
for f in \
  backend/services/seymour_pool_sync_service.py \
  backend/db/repositories/worker_repository.py \
  frontend/js/graph.js \
  backend/jobs/platform_sync_job.py; do
  test -f "$f" && echo "PASS: $f"
done
curl -fsS --max-time 5 'http://192.168.1.169:8561/api/v1/statistics/workers?window=5m' >/dev/null
echo "PASS: Seymour telemetry reachable"
echo "Doctor PASS"
