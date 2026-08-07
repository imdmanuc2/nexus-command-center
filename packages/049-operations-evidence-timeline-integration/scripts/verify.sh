#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
cd "$REPO_ROOT"
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="${NEXUS_DB_PASSWORD:-}"
DB=(psql -q -At -h "${NEXUS_DB_HOST:-localhost}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}")
count="$("${DB[@]}" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('operation_evidence','operation_evidence_events','operation_annotations','operation_evidence_worker_state');")"
test "$count" = '4'
echo 'operation evidence schema PASS'
/usr/bin/python3 -m py_compile backend/db/repositories/operation_evidence_repository.py backend/services/operation_evidence_service.py backend/modules/platform_evidence.py backend/jobs/operation_evidence_worker.py
echo 'Python compilation PASS'
grep -q 'from backend.modules import platform_evidence' backend/api/server.py
grep -q 'Package 049: Operations Evidence & Timeline Integration' backend/api/server.py
echo 'HTTP route registration PASS'
sudo systemctl is-active --quiet nexus-operation-evidence-worker.service
echo 'operation evidence worker PASS'
for _ in $(seq 1 20); do
  curl -fsS http://localhost:8080/api/evidence/status >/tmp/nexus-evidence-status.json && break
  sleep 1
done
jq -e '.status == "ok"' /tmp/nexus-evidence-status.json >/dev/null
echo 'operation evidence status API PASS'
curl -fsS http://localhost:8080/api/evidence | jq -e '.status == "ok"' >/dev/null
curl -fsS http://localhost:8080/api/timeline/operations | jq -e '.status == "ok"' >/dev/null
curl -fsS http://localhost:8080/api/recommendations/context | jq -e '.status == "ok"' >/dev/null
curl -fsS http://localhost:8080/api/assets/nexus-local/operations | jq -e '.status == "ok"' >/dev/null
echo 'operation evidence APIs PASS'
PYTHONPATH="$REPO_ROOT" /usr/bin/python3 - <<'PY'
from backend.services.operation_evidence_service import aggregate_once
result = aggregate_once()
assert result['status'] == 'ok', result
print('operation evidence aggregation PASS')
PY
rows="$("${DB[@]}" -c "SELECT COUNT(*) FROM operation_evidence_worker_state WHERE worker_name='nexus-operation-evidence-worker' AND last_completed_at IS NOT NULL;")"
test "$rows" = '1'
echo 'operation evidence lifecycle PASS'
echo 'Package 049 verification PASS'
