#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
echo "== Operations control endpoints =="
for endpoint in /api/platform/automation/actions /api/platform/automation/runs /api/platform/automation/summary /api/platform/automation/audit; do
  printf '%-48s ' "$endpoint"
  curl --max-time 10 -fsS "http://127.0.0.1:8080$endpoint" | jq -e '.status == "ok"' >/dev/null
  echo PASS
done

echo
echo "== Safe dry-run request =="
ENTITY_ID="package-026-verification-$(date +%s)"
REQUEST="$(curl --max-time 10 -fsS -X POST -H 'Content-Type: application/json' -d "{\"actionId\":\"refresh-platform-sync\",\"entityType\":\"platform\",\"entityId\":\"$ENTITY_ID\",\"requestedBy\":\"package-026-verify\",\"dryRun\":true}" http://127.0.0.1:8080/api/platform/automation/request)"
echo "$REQUEST" | jq .
RUN_ID="$(echo "$REQUEST" | jq -r '.run.runId')"
test -n "$RUN_ID" && test "$RUN_ID" != null

echo
echo "== Process queued dry run =="
curl --max-time 30 -fsS -X POST -H 'Content-Type: application/json' -d '{"limit":25}' http://127.0.0.1:8080/api/platform/automation/process | jq -e '.status == "ok"' >/dev/null
curl --max-time 10 -fsS http://127.0.0.1:8080/api/platform/automation/runs | jq -e --arg run_id "$RUN_ID" '.runs[] | select(.runId == $run_id and .status == "completed" and .dryRun == true)' >/dev/null
echo "Dry-run lifecycle                         PASS"

echo
echo "== PostgreSQL audit =="
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -c "SELECT run_id,control_action,previous_status,new_status,actor,occurred_at FROM nexus.automation_control_audit WHERE run_id='$RUN_ID' ORDER BY occurred_at;"

echo
echo "== Operations Center UI =="
curl --max-time 10 -fsS http://127.0.0.1:8080/operations-center.html | grep -q "Controlled Execution"
curl --max-time 10 -fsS http://127.0.0.1:8080/js/operations-center.js | grep -q "/api/platform/automation/request"
echo "Operations Center controls                PASS"
echo "Package 026 verified."
