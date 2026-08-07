#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
set -a
source "$ROOT/backend/data/private/cmdb.env"
set +a

q(){ PGPASSWORD="$NEXUS_DB_PASSWORD" psql -At -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "$1"; }
json_ok(){ curl --fail --silent --show-error "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ok', d"; }

test "$(q "SELECT to_regclass('nexus.maintenance_history') IS NOT NULL")" = t
echo "maintenance history PASS"

test "$(q "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='maintenance_targets_target_type_check' AND pg_get_constraintdef(oid) LIKE '%service%')")" = t
echo "service maintenance targets PASS"

python3 -m py_compile \
  "$ROOT/backend/db/repositories/maintenance_repository.py" \
  "$ROOT/backend/db/repositories/service_maintenance_repository.py" \
  "$ROOT/backend/services/service_maintenance_service.py" \
  "$ROOT/backend/modules/platform_service_maintenance.py" \
  "$ROOT/backend/api/server.py"
echo "Python compilation PASS"

for route in \
  '/api/maintenance' \
  '/api/maintenance/active' \
  '/api/maintenance/upcoming' \
  '/api/maintenance/history' \
  '/api/maintenance/impact-preview'
do
  grep -q "$route" "$ROOT/backend/api/server.py"
done
echo "maintenance API routes PASS"

grep -q 'Maintenance & Planned Outages' "$ROOT/frontend/service-operations.html"
grep -q 'maintenanceDialog' "$ROOT/frontend/service-operations.html"
echo "Operations Center maintenance UI PASS"

json_ok "http://127.0.0.1:8080/api/maintenance"
echo "maintenance list API PASS"

json_ok "http://127.0.0.1:8080/api/maintenance/active"
echo "active maintenance API PASS"

json_ok "http://127.0.0.1:8080/api/maintenance/upcoming"
echo "upcoming maintenance API PASS"

json_ok "http://127.0.0.1:8080/api/maintenance/history"
echo "maintenance history API PASS"

SERVICE_ID="$(q "SELECT service_id FROM nexus.business_services ORDER BY service_id LIMIT 1")"
test -n "$SERVICE_ID"
json_ok "http://127.0.0.1:8080/api/maintenance/impact-preview?serviceId=$SERVICE_ID"
echo "maintenance impact preview PASS"

echo "Package 044 verified."
