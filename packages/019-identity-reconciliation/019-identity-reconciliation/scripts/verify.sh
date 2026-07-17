#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}";cd "$ROOT"
echo '== Identity integrity ==';python3 -m backend.jobs.identity_reconciliation_job
echo '== Platform inventory sync ==';python3 -m scripts.sync_platform_inventory
echo '== Integrated Platform sync ==';python3 - <<'PY2'
import contextlib,io,json
from backend.jobs.platform_sync_job import run_once
out=io.StringIO()
with contextlib.redirect_stdout(out): result=run_once(stale_seconds=300,dry_run=False)
print(json.dumps({'status':result.get('status'),'timelineEngine':result.get('timelineEngine')},indent=2))
PY2
set -a;source backend/data/private/cmdb.env;set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -P pager=off -c "SELECT worker_id,source_system,source_worker_id,asset_id,pool_instance_id,status,last_seen_at FROM nexus.workers ORDER BY source_system,source_worker_id; SELECT action,COUNT(*) FROM nexus.identity_reconciliation_audit GROUP BY action ORDER BY action;"
echo 'Package 019 verified.'
