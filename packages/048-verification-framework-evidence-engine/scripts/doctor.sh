#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

test -x /usr/bin/python3
test -f backend/db/connection.py
test -f backend/capabilities/registry.py
test -f backend/transports/target_resolver.py
test -f backend/transports/transport_factory.py
test -f backend/db/migrations/036_change_rollback_orchestration_recovery.sql
test -f backend/api/server.py
test -f backend/data/private/cmdb.env
grep -q "class NexusHandler(BaseHTTPRequestHandler)" backend/api/server.py
grep -q "def do_GET(self):" backend/api/server.py
grep -q "def do_POST(self):" backend/api/server.py

set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -q -At -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" \
  -c "SELECT to_regclass('nexus.change_rollback_plans') IS NOT NULL;" | grep -qx t

echo "Package 048 doctor PASS"
/usr/bin/python3 - <<'PYCHK'
from backend.capabilities.registry import get_capability_registry
registry = get_capability_registry()
registry.resolve("host.identity")
print("capability registry PASS")
PYCHK

echo "Package 048 doctor PASS"
