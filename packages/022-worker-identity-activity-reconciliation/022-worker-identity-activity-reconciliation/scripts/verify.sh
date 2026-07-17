#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

echo "== Worker activity reconciliation =="
python3 -m backend.jobs.worker_activity_reconciliation_job

echo
echo "== Integrated Platform sync =="
python3 - <<'PY'
import contextlib
import io
import json

from backend.jobs.platform_sync_job import run_once

captured = io.StringIO()

with contextlib.redirect_stdout(captured):
    result = run_once(stale_seconds=300, dry_run=False)

print(json.dumps({
    "status": result.get("status"),
    "workerActivityReconciliation":
        result.get("workerActivityReconciliation"),
    "eventEngine": result.get("eventEngine"),
    "alertEngine": result.get("alertEngine"),
    "contextBuilder": result.get("contextBuilder"),
    "recommendationEngine": result.get("recommendationEngine"),
    "timelineEngine": result.get("timelineEngine"),
}, indent=2))
PY

echo
echo "== Worker rows =="

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
    worker_id,
    display_name,
    asset_id,
    source_system,
    pool_instance_id,
    status,
    activity_state,
    current_session,
    connection_confirmed,
    telemetry_available,
    current_hashrate,
    shares_per_second
FROM nexus.workers
ORDER BY asset_id NULLS LAST, display_name, worker_id;

SELECT
    COUNT(*) FILTER (
        WHERE current_session = TRUE
          AND activity_state IN ('active', 'idle')
    ) AS active_workers,
    COUNT(DISTINCT asset_id) FILTER (
        WHERE current_session = TRUE
          AND activity_state IN ('active', 'idle')
          AND asset_id IS NOT NULL
    ) AS distinct_active_assets,
    COUNT(*) FILTER (
        WHERE current_session = TRUE
          AND activity_state IN ('active', 'idle')
          AND asset_id IS NULL
    ) AS active_unbound_workers
FROM nexus.workers;

SELECT COUNT(*) AS invalid_offline_metrics
FROM nexus.workers
WHERE (
        activity_state IN ('offline', 'stale', 'unknown')
        OR LOWER(COALESCE(status, '')) IN (
            'offline', 'stale', 'down', 'error'
        )
      )
  AND (
        COALESCE(current_hashrate, 0) <> 0
        OR COALESCE(shares_per_second, 0) <> 0
      );

SELECT asset_id, COUNT(*) AS current_sessions
FROM nexus.workers
WHERE asset_id IS NOT NULL
  AND current_session = TRUE
GROUP BY asset_id
HAVING COUNT(*) > 1;
"

echo
echo "== Platform APIs =="
curl -fsS http://127.0.0.1:8080/api/platform/workers \
  | jq '{
      status,
      count,
      activeCount,
      byActivity,
      invariant
    }'

curl -fsS http://127.0.0.1:8080/api/platform/fleet \
  | jq '{
      status,
      fleetHashrate,
      workers
    }'

curl -fsS http://127.0.0.1:8080/api/platform/topology \
  | jq '{
      status,
      counts
    }'

echo "Package 022 verified."
