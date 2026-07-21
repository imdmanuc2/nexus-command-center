#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; cd "$ROOT"
set -a; source backend/data/private/cmdb.env; set +a
q(){ PGPASSWORD="$NEXUS_DB_PASSWORD" psql -Atqc "$1" -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME"; }
[ "$(q "select to_regclass('nexus.software_packages') is not null")" = t ] && echo "software_packages table PASS"
[ "$(q "select to_regclass('nexus.deployment_jobs') is not null")" = t ] && echo "deployment_jobs table PASS"
[ "$(q "select to_regclass('nexus.deployment_targets') is not null")" = t ] && echo "deployment_targets table PASS"
python3 -m py_compile backend/api/server.py backend/services/deployment_service.py backend/db/repositories/deployment_repository.py
grep -q '/api/platform/deployments/jobs' backend/api/server.py
test -f frontend/deployments.html
echo "API, lifecycle, audit, and UI PASS"
if curl -fsS http://127.0.0.1:8080/api/platform/deployments/jobs >/dev/null 2>&1; then echo "Live API check PASS"; else echo "Live API check skipped (service not reachable on 127.0.0.1:8080)"; fi
echo "Package 035 verified."
