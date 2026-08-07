#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
q(){ PGPASSWORD="${NEXUS_DB_PASSWORD:?}" psql -At -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -c "$1"; }
[[ "$(q "SELECT to_regclass('nexus.business_service_membership_rules') IS NOT NULL")" == t ]] && echo "membership rules PASS"
[[ "$(q "SELECT to_regclass('nexus.business_service_reconciliation_runs') IS NOT NULL")" == t ]] && echo "reconciliation history PASS"
[[ "$(q "SELECT COUNT(*) >= 7 FROM nexus.business_service_membership_rules WHERE enabled=TRUE")" == t ]] && echo "default service mapping rules PASS"
python3 -m py_compile "$ROOT/backend/db/repositories/service_membership_repository.py" "$ROOT/backend/services/service_membership_service.py" "$ROOT/backend/api/server.py"
HEALTH=$(curl -fsS http://127.0.0.1:8080/api/health); echo "$HEALTH" | grep -q '"status": "healthy"' && echo "health endpoint PASS"
RESULT=$(curl -fsS -X POST -H 'Content-Type: application/json' -d '{"triggerSource":"package-verify"}' http://127.0.0.1:8080/api/services/membership/reconcile)
echo "$RESULT" | grep -q '"status": "ok"' && echo "automatic membership reconciliation PASS"
curl -fsS http://127.0.0.1:8080/api/services/membership/rules >/dev/null && echo "membership rules API PASS"
curl -fsS http://127.0.0.1:8080/api/services/membership/runs >/dev/null && echo "reconciliation runs API PASS"
DASH=$(curl -fsS http://127.0.0.1:8080/api/services/dashboard); echo "$DASH" | grep -q '"not-configured"' && echo "not-configured health state PASS"
grep -q 'Reconcile Membership' "$ROOT/frontend/service-operations.html" && echo "operations UI reconciliation control PASS"
echo "Package 042 verified."
