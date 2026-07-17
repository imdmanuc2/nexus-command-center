#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
echo "== Timeline builder =="
python3 -m backend.jobs.platform_timeline_job
set -a; source backend/data/private/cmdb.env; set +a
echo "== Database counts =="
PGPASSWORD="$NEXUS_DB_PASSWORD" psql \
 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" \
 -d "$NEXUS_DB_NAME" -c "
SELECT COUNT(*) timeline_entries FROM nexus.operations_timeline;
SELECT COUNT(*) state_history FROM nexus.asset_state_history;
SELECT source_type,COUNT(*) FROM nexus.operations_timeline
GROUP BY source_type ORDER BY source_type;"
echo "== Timeline APIs =="
curl -fsS http://127.0.0.1:8080/api/platform/timeline | jq '{status,source,count}'
curl -fsS http://127.0.0.1:8080/api/platform/timeline/latest | jq '{status,source,count}'
curl -fsS http://127.0.0.1:8080/api/platform/timeline/summary | jq
echo "== Integrated sync =="
python3 - <<'PY'
import contextlib,io,json
from backend.jobs.platform_sync_job import run_once
out=io.StringIO()
with contextlib.redirect_stdout(out):
    result=run_once(stale_seconds=300,dry_run=False)
print(json.dumps({"status":result.get("status"),
                  "timelineEngine":result.get("timelineEngine")},indent=2))
PY
echo "Package 018 verified."
