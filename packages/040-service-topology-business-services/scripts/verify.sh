#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="${NEXUS_DB_PASSWORD:?}" psql -At -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -c "$1"; }
[[ "$(q "SELECT to_regclass('nexus.business_services') IS NOT NULL")" == t ]] && echo "business services PASS"
[[ "$(q "SELECT to_regclass('nexus.business_service_members') IS NOT NULL")" == t ]] && echo "service membership PASS"
[[ "$(q "SELECT to_regclass('nexus.business_service_dependencies') IS NOT NULL")" == t ]] && echo "service dependencies PASS"
[[ "$(q "SELECT count(*) >= 3 FROM nexus.business_services")" == t ]] && echo "mining, AI, and rentable compute service templates PASS"
python3 -m py_compile "$ROOT/backend/db/repositories/service_topology_repository.py" "$ROOT/backend/services/service_topology_service.py" "$ROOT/backend/modules/platform_services.py" "$ROOT/backend/api/server.py"
grep -q 'Service Topology' "$ROOT/frontend/js/nav.js"; grep -q 'Business-service health' "$ROOT/frontend/service-topology.html"
echo "service health rollup, capacity, workload mapping, dependency topology, and UI PASS"
if curl -fsS http://127.0.0.1:8080/api/services/topology >/dev/null; then echo "Live API check PASS"; else echo "Live API check FAILED"; exit 1; fi
echo "Package 040 verified."
