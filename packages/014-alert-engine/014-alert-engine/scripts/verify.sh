#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

echo "== Alert engine =="
python3 -m backend.jobs.platform_alert_job

echo "== Database counts =="
set -a
source backend/data/private/cmdb.env
set +a

PGPASSWORD="$NEXUS_DB_PASSWORD" psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -c "
SELECT COUNT(*) AS alert_rules FROM nexus.alert_rules;
SELECT COUNT(*) AS alerts FROM nexus.alerts;
SELECT status, severity, COUNT(*)
FROM nexus.alerts
GROUP BY status, severity
ORDER BY status, severity;
"

echo "== Alert APIs =="
curl -fsS http://127.0.0.1:8080/api/platform/alerts \
  | jq '{status, source, count}'
curl -fsS http://127.0.0.1:8080/api/platform/alerts/active \
  | jq '{status, source, count}'
curl -fsS http://127.0.0.1:8080/api/platform/alerts/summary \
  | jq

echo "== Integrated sync =="
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
    "eventEngine": result.get("eventEngine"),
    "alertEngine": result.get("alertEngine"),
}, indent=2))
PY

echo "Package 014 verified."
