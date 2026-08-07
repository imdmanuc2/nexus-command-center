#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$(cd "$PKG_DIR/../.." && pwd)"; set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a; export PGPASSWORD="$NEXUS_DB_PASSWORD"; PSQL=(psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -At)
"${PSQL[@]}" -c "SELECT to_regclass('nexus.change_rollback_plans') IS NOT NULL" | grep -qx t; "${PSQL[@]}" -c "SELECT to_regclass('nexus.change_rollback_attempts') IS NOT NULL" | grep -qx t; "${PSQL[@]}" -c "SELECT to_regclass('nexus.change_rollback_events') IS NOT NULL" | grep -qx t; echo 'change rollback schema PASS'
python3 -m py_compile "$ROOT/backend/api/server.py" "$ROOT/backend/db/repositories/change_rollback_repository.py" "$ROOT/backend/services/change_rollback_service.py" "$ROOT/backend/modules/platform_change_rollback.py" "$ROOT/backend/jobs/change_rollback_worker.py"; echo 'Python compilation PASS'
sleep 3; sudo systemctl is-active --quiet nexus-change-rollback-worker.service; RESTARTS="$(systemctl show nexus-change-rollback-worker.service -p NRestarts --value)"; test "${RESTARTS:-0}" -lt 3; echo 'change rollback worker service PASS'
grep -q 'from backend.modules import platform_change_rollback' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/status' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/history' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/approve' "$ROOT/backend/api/server.py"
grep -q '/api/change-rollbacks/queue' "$ROOT/backend/api/server.py"
curl -fsS http://127.0.0.1:8080/api/change-rollbacks/status | grep -q '"status"'; curl -fsS http://127.0.0.1:8080/api/change-rollbacks/history | grep -q '"rollbacks"'; echo 'change rollback APIs PASS'
CHANGE_ID="$("${PSQL[@]}" -c "INSERT INTO nexus.change_requests (change_number,title,description,change_type,risk_level,status,requested_by,implementation_plan,rollback_plan,validation_plan,created_at,updated_at) VALUES ('VERIFY-047-'||extract(epoch from now())::bigint,'Package 047 verification','Temporary rollback lifecycle verification','standard','low','failed','package-047','{}'::jsonb,'{}'::jsonb,'{}'::jsonb,NOW(),NOW()) RETURNING change_id;")"
CREATE_JSON="$(curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"changeId\":\"$CHANGE_ID\",\"rollbackAction\":\"host.identity\",\"targetType\":\"host\",\"targetId\":\"localhost\",\"assetId\":\"localhost\",\"parameters\":{\"transport\":\"local\"},\"reason\":\"Package 047 verification\",\"requestedBy\":\"package-047\"}" http://127.0.0.1:8080/api/change-rollbacks)"
ROLLBACK_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["rollback"]["rollback_id"])' <<<"$CREATE_JSON")"
curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"rollbackId\":\"$ROLLBACK_ID\",\"approvedBy\":\"package-047\"}" http://127.0.0.1:8080/api/change-rollbacks/approve | grep -q '"approved"'
curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"rollbackId\":\"$ROLLBACK_ID\",\"requestedBy\":\"package-047\"}" http://127.0.0.1:8080/api/change-rollbacks/queue | grep -q '"queued"'
cd "$ROOT"; python3 -m backend.jobs.change_rollback_worker --once | grep -q '"succeeded"'
"${PSQL[@]}" -c "SELECT status FROM nexus.change_rollback_plans WHERE rollback_id='$ROLLBACK_ID'" | grep -qx succeeded; "${PSQL[@]}" -c "SELECT rollback_status FROM nexus.change_requests WHERE change_id='$CHANGE_ID'" | grep -qx succeeded; "${PSQL[@]}" -c "SELECT COUNT(*) FROM nexus.change_rollback_attempts WHERE rollback_id='$ROLLBACK_ID'" | grep -qx 1; echo 'plan, approve, queue, execute, verify lifecycle PASS'
"${PSQL[@]}" -c "DELETE FROM nexus.change_rollback_plans WHERE rollback_id='$ROLLBACK_ID'"; "${PSQL[@]}" -c "DELETE FROM nexus.change_requests WHERE change_id='$CHANGE_ID'"; echo 'verification cleanup PASS'; echo 'Package 047 verified.'
