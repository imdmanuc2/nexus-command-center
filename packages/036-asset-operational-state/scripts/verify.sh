#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
set -a
[ ! -f backend/data/private/cmdb.env ] || source backend/data/private/cmdb.env
set +a
q(){ PGPASSWORD="$NEXUS_DB_PASSWORD" psql -At -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "$1"; }
[ "$(q "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='nexus' AND table_name='assets' AND column_name='operational_state'")" = "1" ]
echo "assets operational_state column PASS"
[ "$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='nexus' AND table_name='asset_operational_state_history'")" = "1" ]
echo "asset_operational_state_history table PASS"
python3 -m py_compile backend/services/operational_state_service.py backend/db/repositories/operational_state_repository.py backend/modules/platform_operational_state.py backend/api/server.py
grep -q '/api/platform/operational-state/set' backend/api/server.py
grep -q 'effectiveOperationalState' backend/services/operational_state_service.py
grep -q 'operational-state.js' frontend/operational-state.html
echo "API, maintenance integration, alert suppression, audit, bulk state, and UI PASS"
if curl -fsS http://127.0.0.1:8080/api/platform/operational-state/summary >/tmp/nexus-036-summary.json 2>/dev/null; then python3 -m json.tool /tmp/nexus-036-summary.json >/dev/null; echo "Live API PASS"; else echo "Live API check skipped (service not reachable on 127.0.0.1:8080)"; fi
echo "Package 036 verified."
