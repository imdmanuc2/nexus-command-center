#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
set -a
source "$ROOT/backend/data/private/cmdb.env"
set +a
PSQL=(psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -At)
export PGPASSWORD="$NEXUS_DB_PASSWORD"

"${PSQL[@]}" -c "SELECT to_regclass('nexus.operation_queue') IS NOT NULL" | grep -qx t
"${PSQL[@]}" -c "SELECT to_regclass('nexus.operation_queue_events') IS NOT NULL" | grep -qx t
"${PSQL[@]}" -c "SELECT to_regclass('nexus.change_execution_workers') IS NOT NULL" | grep -qx t
"${PSQL[@]}" -c "SELECT to_regclass('nexus.change_execution_attempts') IS NOT NULL" | grep -qx t
echo "change execution schema PASS"

python3 -m py_compile \
  "$ROOT/backend/api/server.py" \
  "$ROOT/backend/db/repositories/change_execution_repository.py" \
  "$ROOT/backend/services/change_execution_service.py" \
  "$ROOT/backend/jobs/change_execution_worker.py"
echo "Python compilation PASS"

sleep 3
sudo systemctl is-active --quiet nexus-change-execution-worker.service
RESTARTS="$(systemctl show nexus-change-execution-worker.service -p NRestarts --value)"
test "${RESTARTS:-0}" -lt 3
echo "change execution worker service PASS"

curl -fsS http://127.0.0.1:8080/api/change-execution/status | grep -q '"status"'
curl -fsS http://127.0.0.1:8080/api/change-execution/history | grep -q '"status"'
echo "change execution APIs PASS"

OP_ID="package-046-verification-$(date +%s)"
"${PSQL[@]}" -c "
INSERT INTO nexus.operation_queue
(operation_id,action_name,target_type,target_id,asset_id,status,priority,correlation_id,
 idempotency_key,triggered_by_type,triggered_by_id,read_only,confirmation_required,
 confirmed,input_data,summary,timeout_seconds,scheduled_for,queued_at,total_steps)
VALUES
('$OP_ID','host.identity','asset','package-028-verification',NULL,'queued',1,
 '$OP_ID','$OP_ID','system','package-046',TRUE,FALSE,TRUE,
 '{\"parameters\":{\"transport\":\"local\"}}'::jsonb,
 'Package 046 verification',15,NOW(),NOW(),4);
"

PYTHON_BIN="$ROOT/venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="$(command -v python3)"
cd "$ROOT"
PYTHONPATH="$ROOT" "$PYTHON_BIN" -m backend.jobs.change_execution_worker \
  --once --worker-id package-046-verifier >/tmp/package-046-worker.out

"${PSQL[@]}" -c "SELECT status FROM nexus.operation_queue WHERE operation_id='$OP_ID'" | grep -qx succeeded
"${PSQL[@]}" -c "SELECT COUNT(*) FROM nexus.change_execution_attempts WHERE operation_id='$OP_ID' AND status='succeeded'" | grep -qx 1
echo "claim, execute, verify lifecycle PASS"

"${PSQL[@]}" -c "DELETE FROM nexus.operation_queue_events WHERE operation_id='$OP_ID'; DELETE FROM nexus.change_execution_attempts WHERE operation_id='$OP_ID'; DELETE FROM nexus.operation_queue WHERE operation_id='$OP_ID'; DELETE FROM nexus.change_execution_workers WHERE worker_id='package-046-verifier';"
echo "verification cleanup PASS"
echo "Package 046 verified."
