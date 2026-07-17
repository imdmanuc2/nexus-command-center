#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
echo "== Create safe dry-run automation =="
python3 - <<'PY2'
import json
from backend.services.automation_engine_service import request_automation
print(json.dumps(request_automation(action_id='refresh-resource-sync',entity_type='platform',entity_id='primary',requested_by='package-017-verifier',dry_run=True),indent=2))
PY2
echo "== Process queue ==";python3 -m backend.jobs.platform_automation_job
set -a;source backend/data/private/cmdb.env;set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "SELECT COUNT(*) AS automation_actions FROM nexus.automation_actions; SELECT status,COUNT(*) FROM nexus.automation_runs GROUP BY status ORDER BY status;"
for e in actions runs summary; do curl -fsS "http://127.0.0.1:8080/api/platform/automation/$e" | jq '{status,source,count,pendingApproval,queued,running,completed,failed}'; done
echo "== Integrated sync =="
python3 - <<'PY2'
import contextlib,io,json
from backend.jobs.platform_sync_job import run_once
b=io.StringIO()
with contextlib.redirect_stdout(b): r=run_once(stale_seconds=300,dry_run=False)
print(json.dumps({'status':r.get('status'),'automationEngine':r.get('automationEngine')},indent=2))
PY2
echo "Package 017 verified."
