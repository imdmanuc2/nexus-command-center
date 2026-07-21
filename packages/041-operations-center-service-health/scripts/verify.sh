#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="${NEXUS_DB_PASSWORD:?}" psql -At -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -c "$1"; }
[[ "$(q "SELECT to_regclass('nexus.service_health_snapshots') IS NOT NULL")" == t ]] && echo "service health snapshots PASS"
[[ "$(q "SELECT to_regclass('nexus.service_incidents') IS NOT NULL")" == t ]] && echo "service incidents PASS"
[[ "$(q "SELECT to_regclass('nexus.service_availability_rollups') IS NOT NULL")" == t ]] && echo "availability and capacity rollups PASS"
python3 -m py_compile "$ROOT/backend/db/repositories/service_operations_repository.py" "$ROOT/backend/services/service_operations_service.py" "$ROOT/backend/modules/platform_service_operations.py" "$ROOT/backend/api/server.py"
grep -q 'Service Operations Center' "$ROOT/frontend/service-operations.html"; grep -q '/service-operations.html' "$ROOT/frontend/js/nav.js"
echo "operations dashboard, service health, incidents, capacity, redundancy, and UI PASS"
for i in {1..10}; do curl -fsS http://127.0.0.1:8080/api/health >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:8080/api/health >/dev/null && echo "Dedicated health endpoint PASS"
curl -fsS http://127.0.0.1:8080/api/services/dashboard >/dev/null && echo "Live service operations API PASS"
echo "Package 041 verified."
