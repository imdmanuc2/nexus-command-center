#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

echo "== Executor registry =="
python3 - <<'PY'
from backend.executors.registry import get_executor_registry

registry = get_executor_registry()
items = {item["name"]: item["actions"] for item in registry.describe()}
assert "bitcoin" in items
assert "test-blockchain-rpc" in items["bitcoin"]
assert "bitcoin.check-sync" in items["bitcoin"]
assert "bitcoin.verify-wallet" in items["bitcoin"]
assert "bitcoin.collect-diagnostics" in items["bitcoin"]
print("Managed executor registry                  PASS")
PY

echo
echo "== Catalog actions =="
ACTIONS="$(curl --max-time 10 -fsS \
  http://127.0.0.1:8080/api/platform/automation/actions)"

echo "$ACTIONS" | jq -e '
  [.actions[].actionId] as $ids
  | ($ids | index("bitcoin.check-sync")) != null
  and ($ids | index("bitcoin.verify-wallet")) != null
  and ($ids | index("bitcoin.collect-diagnostics")) != null
' >/dev/null

echo "Bitcoin executor action catalog            PASS"

echo
echo "== Managed executor dry run =="
REQUEST="$(curl --max-time 10 -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{
    "actionId":"bitcoin.collect-diagnostics",
    "entityType":"blockchain-node",
    "entityId":"package-027-verification",
    "requestedBy":"package-027-verify",
    "dryRun":true,
    "inputPayload":{"coin":"BTC"}
  }' \
  http://127.0.0.1:8080/api/platform/automation/request)"

RUN_ID="$(echo "$REQUEST" | jq -r '.run.runId')"
test -n "$RUN_ID"
test "$RUN_ID" != null

curl --max-time 30 -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"limit":25}' \
  http://127.0.0.1:8080/api/platform/automation/process \
  | jq -e '.status == "ok"' >/dev/null

curl --max-time 10 -fsS \
  http://127.0.0.1:8080/api/platform/automation/runs \
  | jq -e --arg run_id "$RUN_ID" '
      .runs[]
      | select(
          .runId == $run_id
          and .status == "completed"
          and .resultPayload.status == "dry-run-complete"
        )
    ' >/dev/null

echo "Managed executor dry-run lifecycle         PASS"

echo
echo "== Migration =="
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"

psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -Atc "SELECT version FROM schema_migrations WHERE version='018'" \
  | grep -q '^018$'

echo "Migration 018                              PASS"
echo "Package 027 verified."
