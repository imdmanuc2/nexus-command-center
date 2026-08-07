#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="$NEXUS_DB_PASSWORD" psql -At -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "$1"; }
json_ok(){ curl --fail --silent --show-error "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ok', d"; }

for t in change_templates change_requests change_steps change_approvals change_execution_log; do
  test "$(q "SELECT to_regclass('nexus.$t') IS NOT NULL")" = t
done
echo "change-management schema PASS"

test "$(q "SELECT data_type FROM information_schema.columns WHERE table_schema='nexus' AND table_name='change_requests' AND column_name='operation_id'")" = text
echo "optional Operations Queue reference PASS"

python3 -m py_compile "$ROOT/backend/db/repositories/change_management_repository.py" "$ROOT/backend/services/change_management_service.py" "$ROOT/backend/modules/platform_change_management.py" "$ROOT/backend/api/server.py"
echo "Python compilation PASS"

for route in '/api/changes' '/api/changes/history' '/api/changes/templates' '/api/changes/impact-preview'; do grep -q "$route" "$ROOT/backend/api/server.py"; done
echo "change API routes PASS"

grep -q "def _read_json_body(self):" "$ROOT/backend/api/server.py"
echo "JSON request-body compatibility PASS"

grep -q 'Change Management' "$ROOT/frontend/service-operations.html"
grep -q 'changeDialog' "$ROOT/frontend/service-operations.html"
echo "Operations Center change UI PASS"

json_ok http://127.0.0.1:8080/api/changes
json_ok http://127.0.0.1:8080/api/changes/history
json_ok http://127.0.0.1:8080/api/changes/templates
echo "change read APIs PASS"

ASSET_ID="$(q "SELECT asset_id FROM nexus.assets ORDER BY asset_id LIMIT 1")"
test -n "$ASSET_ID"
json_ok "http://127.0.0.1:8080/api/changes/impact-preview?targetType=asset&targetId=$ASSET_ID"
echo "change impact preview PASS"

RESP="$(curl --fail --silent --show-error -X POST http://127.0.0.1:8080/api/changes -H 'Content-Type: application/json' -d "{\"templateId\":\"host-identity\",\"title\":\"Package 045 verification\",\"targetType\":\"asset\",\"targetId\":\"$ASSET_ID\",\"assetId\":\"$ASSET_ID\",\"requestedBy\":\"package-045-verify\"}")"
CHANGE_ID="$(printf '%s' "$RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ok',d; print(d['change']['changeId'])")"
test -n "$CHANGE_ID"
json_ok "http://127.0.0.1:8080/api/changes/$CHANGE_ID"
echo "change create/read lifecycle PASS"

PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" <<SQL >/dev/null
DELETE FROM nexus.change_requests WHERE change_id='$CHANGE_ID';
SQL
echo "verification cleanup PASS"
echo "Package 045 verified."
