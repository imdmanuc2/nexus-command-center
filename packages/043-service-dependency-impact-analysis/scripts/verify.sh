#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="$NEXUS_DB_PASSWORD" psql -At -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "$1"; }
test "$(q "SELECT to_regclass('nexus.service_impact_snapshots') IS NOT NULL")" = t && echo "impact snapshots PASS"
test "$(q "SELECT to_regclass('nexus.service_dependency_rules') IS NOT NULL")" = t && echo "dependency rules PASS"
test "$(q "SELECT COUNT(*) >= 4 FROM nexus.service_dependency_rules WHERE active=TRUE")" = t && echo "default dependency rules PASS"
python3 -m py_compile "$ROOT/backend/db/repositories/service_impact_repository.py" "$ROOT/backend/services/service_impact_service.py" "$ROOT/backend/modules/platform_service_impact.py" "$ROOT/backend/api/server.py"
grep -q '/api/services/dependencies' "$ROOT/backend/api/server.py" && echo "dependencies API route PASS"
grep -q '/api/services/impact' "$ROOT/backend/api/server.py" && echo "impact API route PASS"
grep -q '/api/services/root-cause' "$ROOT/backend/api/server.py" && echo "root cause API route PASS"
grep -q 'Dependency impact analysis' "$ROOT/frontend/service-operations.html" && echo "operations UI impact panel PASS"
curl -fsS http://127.0.0.1:8080/api/services/dependencies | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'" && echo "dependency analysis PASS"
curl -fsS http://127.0.0.1:8080/api/services/impact | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok' and 'services' in d" && echo "service impact analysis PASS"
curl -fsS http://127.0.0.1:8080/api/services/root-cause | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'" && echo "root cause analysis PASS"
echo "Package 043 verified."
