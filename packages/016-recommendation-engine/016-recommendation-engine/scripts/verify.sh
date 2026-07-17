#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

echo "== Recommendation engine =="
python3 -m backend.jobs.platform_recommendation_job

echo "== Database counts =="
set -a
source backend/data/private/cmdb.env
set +a

PGPASSWORD="$NEXUS_DB_PASSWORD" \
psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -c "
SELECT COUNT(*) AS recommendations
FROM nexus.recommendations;

SELECT
    status,
    priority,
    COUNT(*)
FROM nexus.recommendations
GROUP BY status, priority
ORDER BY status, priority;
"

echo "== Recommendation APIs =="
curl -fsS http://127.0.0.1:8080/api/platform/recommendations \
  | jq '{status, source, count}'

curl -fsS \
  http://127.0.0.1:8080/api/platform/recommendations/high-priority \
  | jq '{status, source, count}'

curl -fsS \
  http://127.0.0.1:8080/api/platform/recommendations/summary \
  | jq

echo "== Integrated sync =="
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
    "recommendationEngine": result.get("recommendationEngine"),
}, indent=2))
PY

echo "Package 016 verified."
