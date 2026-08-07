#!/usr/bin/env bash
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"

set -a
source "$ROOT/backend/data/private/cmdb.env"
set +a

export PGPASSWORD="$NEXUS_DB_PASSWORD"

PSQL=(
  psql -q
  -h "$NEXUS_DB_HOST"
  -p "$NEXUS_DB_PORT"
  -U "$NEXUS_DB_USER"
  -d "$NEXUS_DB_NAME"
  -v ON_ERROR_STOP=1
  -At
)

cleanup() {
  if [[ -n "${CHANGE_ID:-}" ]]; then
    "${PSQL[@]}" -c "
      DELETE FROM nexus.change_requests
      WHERE change_id = '$CHANGE_ID'::uuid;
    " >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

"${PSQL[@]}" -c "SELECT to_regclass('nexus.change_rollback_plans') IS NOT NULL" | grep -qx t
"${PSQL[@]}" -c "SELECT to_regclass('nexus.change_rollback_attempts') IS NOT NULL" | grep -qx t
"${PSQL[@]}" -c "SELECT to_regclass('nexus.change_rollback_events') IS NOT NULL" | grep -qx t
echo "change rollback schema PASS"

python3 -m py_compile \
  "$ROOT/backend/api/server.py" \
  "$ROOT/backend/db/repositories/change_rollback_repository.py" \
  "$ROOT/backend/services/change_rollback_service.py" \
  "$ROOT/backend/modules/platform_change_rollback.py" \
  "$ROOT/backend/jobs/change_rollback_worker.py" \
  "$ROOT/backend/transports/target_resolver.py"
echo "Python compilation PASS"

sudo systemctl is-active --quiet nexus-api.service
sudo systemctl is-active --quiet nexus-change-rollback-worker.service

RESTARTS="$(systemctl show nexus-change-rollback-worker.service -p NRestarts --value)"
test "${RESTARTS:-0}" -lt 3
echo "change rollback worker service PASS"

grep -q 'from backend.modules import platform_change_rollback' "$ROOT/backend/api/server.py"
grep -q '"/api/change-rollbacks/status": platform_change_rollback.status' "$ROOT/backend/api/server.py"
grep -q '"/api/change-rollbacks/history": platform_change_rollback.history' "$ROOT/backend/api/server.py"
grep -q 'parsed.path == "/api/change-rollbacks"' "$ROOT/backend/api/server.py"
grep -q 'parsed.path == "/api/change-rollbacks/approve"' "$ROOT/backend/api/server.py"
grep -q 'parsed.path == "/api/change-rollbacks/queue"' "$ROOT/backend/api/server.py"

curl -fsS http://127.0.0.1:8080/api/change-rollbacks/status | grep -q '"status"'
curl -fsS http://127.0.0.1:8080/api/change-rollbacks/history | grep -q '"rollbacks"'
echo "change rollback APIs PASS"

grep -q 'asset_id not in {"nexus-local", "package-028-verification"}' \
  "$ROOT/backend/transports/target_resolver.py"

CHANGE_ID="$("${PSQL[@]}" -c "
INSERT INTO nexus.change_requests (
  change_number,
  title,
  description,
  capability,
  rollback_capability,
  target_type,
  target_id,
  status,
  risk_level,
  requested_by,
  parameters,
  created_at,
  updated_at
)
VALUES (
  'VERIFY-047-R4-' || extract(epoch from clock_timestamp())::bigint,
  'Package 047 R4 verification',
  'Temporary rollback lifecycle verification',
  'host.identity',
  'host.identity',
  'host',
  'nexus-local',
  'failed',
  'low',
  'package-047-r4',
  '{}'::jsonb,
  NOW(),
  NOW()
)
RETURNING change_id;
")"

CREATE_JSON="$(curl -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{
    \"changeId\":\"$CHANGE_ID\",
    \"rollbackAction\":\"host.identity\",
    \"targetType\":\"host\",
    \"targetId\":\"nexus-local\",
    \"assetId\":\"nexus-local\",
    \"parameters\":{\"transport\":\"local\"},
    \"reason\":\"Package 047 R4 verification\",
    \"requestedBy\":\"package-047-r4\"
  }" \
  http://127.0.0.1:8080/api/change-rollbacks
)"

ROLLBACK_ID="$(python3 -c \
  'import json,sys; print(json.load(sys.stdin)["rollback"]["rollback_id"])' \
  <<<"$CREATE_JSON"
)"

curl -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"rollbackId\":\"$ROLLBACK_ID\",\"approvedBy\":\"package-047-r4\"}" \
  http://127.0.0.1:8080/api/change-rollbacks/approve \
  | grep -q '"approved"'

curl -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"rollbackId\":\"$ROLLBACK_ID\",\"requestedBy\":\"package-047-r4\"}" \
  http://127.0.0.1:8080/api/change-rollbacks/queue \
  | grep -q '"queued"'

FINAL_STATUS=""
for _ in $(seq 1 45); do
  FINAL_STATUS="$("${PSQL[@]}" -c "
    SELECT status
    FROM nexus.change_rollback_plans
    WHERE rollback_id = '$ROLLBACK_ID'::uuid;
  ")"

  case "$FINAL_STATUS" in
    succeeded)
      break
      ;;
    failed|manual_intervention|cancelled)
      ERROR_MESSAGE="$("${PSQL[@]}" -c "
        SELECT error_message
        FROM nexus.change_rollback_plans
        WHERE rollback_id = '$ROLLBACK_ID'::uuid;
      ")"
      echo "Rollback verification failed: status=$FINAL_STATUS error=$ERROR_MESSAGE" >&2
      exit 1
      ;;
  esac

  sleep 1
done

if [[ "$FINAL_STATUS" != "succeeded" ]]; then
  echo "Rollback verification timed out: rollback_id=$ROLLBACK_ID status=${FINAL_STATUS:-missing}" >&2
  exit 1
fi

"${PSQL[@]}" -c "
SELECT COUNT(*) > 0
FROM nexus.change_rollback_attempts
WHERE rollback_id = '$ROLLBACK_ID'::uuid
  AND status = 'succeeded';
" | grep -qx t

"${PSQL[@]}" -c "
SELECT COUNT(*) >= 5
FROM nexus.change_rollback_events
WHERE rollback_id = '$ROLLBACK_ID'::uuid
  AND event_type IN ('created','approved','queued','claimed','succeeded');
" | grep -qx t

"${PSQL[@]}" -c "
SELECT
  verification_status = 'passed'
  AND recovery_status = 'recovered'
  AND completed_at IS NOT NULL
FROM nexus.change_rollback_plans
WHERE rollback_id = '$ROLLBACK_ID'::uuid;
" | grep -qx t

echo "change rollback lifecycle PASS"

cleanup
CHANGE_ID=""

echo "Package 047 R4 verification PASS"
