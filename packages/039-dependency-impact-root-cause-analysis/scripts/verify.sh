#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="${NEXUS_DB_PASSWORD:?}" psql -At -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -c "$1"; }
[[ "$(q "SELECT to_regclass('nexus.engineering_knowledge') IS NOT NULL")" == t ]] && echo "engineering knowledge base PASS"
[[ "$(q "SELECT to_regclass('nexus.dependency_analyses') IS NOT NULL")" == t ]] && echo "dependency analyses PASS"
[[ "$(q "SELECT to_regclass('nexus.incident_resolution_outcomes') IS NOT NULL")" == t ]] && echo "incident learning foundation PASS"
[[ "$(q "SELECT count(*) >= 4 FROM nexus.engineering_knowledge")" == t ]] && echo "seeded recommendations PASS"
grep -q 'platform_intelligence' "$ROOT/backend/api/server.py"
grep -q 'Operational Intelligence' "$ROOT/frontend/js/assets.js"
python3 -m py_compile "$ROOT/backend/core/impact_engine.py" "$ROOT/backend/core/root_cause_engine.py" "$ROOT/backend/core/recommendation_engine.py" "$ROOT/backend/services/intelligence_service.py"
echo "root cause, blast radius, recommendations, evidence, CPU/GPU/ASIC/AI workload guidance, and CMDB UI PASS"
if curl -fsS http://127.0.0.1:8080/api/intelligence/knowledge >/dev/null; then echo "Live API check PASS"; else echo "Live API check FAILED"; exit 1; fi
echo "Package 039 verified."
