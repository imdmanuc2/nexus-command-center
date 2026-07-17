#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

echo "== Canonical worker propagation =="
grep -nA8 -B4 \
  'saved_worker = upsert_worker' \
  scripts/sync_platform_inventory.py

echo
echo "== Platform inventory sync =="
python3 -m scripts.sync_platform_inventory

echo
echo "== Integrated Platform sync =="
python3 - <<'PY'
import contextlib
import io
import json

from backend.jobs.platform_sync_job import run_once

captured = io.StringIO()

with contextlib.redirect_stdout(captured):
    result = run_once(
        stale_seconds=300,
        dry_run=False,
    )

print(json.dumps({
    "status": result.get("status"),
    "timelineEngine": result.get("timelineEngine"),
    "automationEngine": result.get("automationEngine"),
}, indent=2))
PY

echo
echo "== Referential integrity =="

set -a
source backend/data/private/cmdb.env
set +a

PGPASSWORD="$NEXUS_DB_PASSWORD" \
psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -P pager=off \
  -c "
SELECT
    w.worker_id,
    w.source_system,
    w.source_worker_id,
    COUNT(l.workload_id) AS workload_count
FROM nexus.workers w
LEFT JOIN nexus.workloads l
  ON l.worker_id = w.worker_id
GROUP BY
    w.worker_id,
    w.source_system,
    w.source_worker_id
ORDER BY
    w.source_system,
    w.source_worker_id;

SELECT COUNT(*) AS orphaned_workloads
FROM nexus.workloads l
LEFT JOIN nexus.workers w
  ON w.worker_id = l.worker_id
WHERE l.worker_id IS NOT NULL
  AND w.worker_id IS NULL;
"

echo "Package 020 verified."
