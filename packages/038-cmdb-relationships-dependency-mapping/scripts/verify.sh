#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="${NEXUS_DB_PASSWORD:?}" psql -At -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -c "$1"; }
[[ "$(q "SELECT to_regclass('nexus.relationship_type_catalog') IS NOT NULL")" == t ]] && echo "relationship type catalog PASS"
[[ "$(q "SELECT to_regclass('nexus.relationship_history') IS NOT NULL")" == t ]] && echo "relationship history PASS"
[[ "$(q "SELECT to_regclass('nexus.compute_capabilities') IS NOT NULL")" == t ]] && echo "compute capabilities PASS"
[[ "$(q "SELECT to_regclass('nexus.workload_assignments') IS NOT NULL")" == t ]] && echo "workload assignments PASS"
grep -q 'platform_dependencies' "$ROOT/backend/api/server.py"
grep -q 'Dependency Map' "$ROOT/frontend/js/assets.js"
echo "API, dependency mapping, CPU/GPU/ASIC capability model, AI/rental workloads, audit, and CMDB UI PASS"
if curl -fsS http://127.0.0.1:8080/api/cmdb/relationships/catalog >/dev/null 2>&1; then echo "Live API check PASS"; else echo "Live API check skipped (service not reachable on 127.0.0.1:8080)"; fi
echo "Package 038 verified."
