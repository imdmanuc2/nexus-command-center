#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"; export PYTHONPATH="$ROOT"
set -a; source backend/data/private/cmdb.env; set +a

required_columns() {
  local table="$1"; shift
  for column in "$@"; do
    local count
    count=$(PGPASSWORD="$NEXUS_DB_PASSWORD" psql -At -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='nexus' AND table_name='${table}' AND column_name='${column}'")
    [[ "$count" == "1" ]] || { echo "${table}.${column} FAIL"; exit 1; }
  done
  echo "${table} columns PASS"
}

required_columns playbooks playbook_id name description category risk_level current_version enabled source_path created_at updated_at
required_columns playbook_versions playbook_id version definition definition_hash created_at
required_columns playbook_runs run_id playbook_id playbook_version operation_session_id target_asset_id target_type status requested_by variables result error_message started_at completed_at created_at updated_at
required_columns playbook_steps step_run_id run_id step_id position capability status parameters result error_message started_at completed_at

python3 - <<'PY'
from backend.playbooks.catalog import get_playbook_catalog
from backend.modules import platform_playbooks
items=get_playbook_catalog().list(); assert len(items)>=6
assert all(x['stepCount']>=2 for x in items)
payload=platform_playbooks.catalog(); assert payload['count']>=6
print('Playbook catalog and database synchronization PASS')
PY

grep -q 'platform_playbooks' backend/api/server.py
grep -q '/api/playbooks/run' backend/api/server.py
grep -q 'Enterprise Playbooks' frontend/playbooks.html
echo "API routes PASS"
echo "Playbooks UI PASS"
echo "Package 030 verified."
