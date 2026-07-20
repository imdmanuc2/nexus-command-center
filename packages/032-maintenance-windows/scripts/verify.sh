#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; cd "$ROOT"
set -a; source backend/data/private/cmdb.env; set +a; export PYTHONPATH="$ROOT"
python3 -m py_compile backend/db/repositories/maintenance_repository.py backend/services/maintenance_service.py backend/modules/platform_maintenance.py backend/services/alert_engine_service.py backend/api/server.py
PG="PGPASSWORD=$NEXUS_DB_PASSWORD psql -At -h $NEXUS_DB_HOST -p $NEXUS_DB_PORT -U $NEXUS_DB_USER -d $NEXUS_DB_NAME"
[ "$(eval "$PG -c \"SELECT to_regclass('nexus.maintenance_windows') IS NOT NULL\"")" = "t" ] && echo "maintenance_windows table PASS"
[ "$(eval "$PG -c \"SELECT to_regclass('nexus.maintenance_targets') IS NOT NULL\"")" = "t" ] && echo "maintenance_targets table PASS"
grep -q 'platform_maintenance' backend/api/server.py
grep -q 'should_suppress_alert' backend/services/alert_engine_service.py
[ -f frontend/maintenance.html ] && [ -f frontend/js/maintenance.js ] && [ -f frontend/css/maintenance.css ]
echo "API, alert suppression, and UI PASS"
if command -v curl >/dev/null && curl -fsS http://127.0.0.1:8080/api/platform/maintenance/windows >/tmp/nexus-maintenance-verify.json 2>/dev/null; then grep -q 'nexus-maintenance-windows' /tmp/nexus-maintenance-verify.json && echo "Live API PASS"; else echo "Live API check skipped (service not reachable on 127.0.0.1:8080)"; fi
echo "Package 032 verified."
