#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
for f in \
  backend/api/server.py \
  backend/services/service_impact_service.py \
  backend/services/service_maintenance_service.py \
  frontend/service-operations.html \
  backend/data/private/cmdb.env
do test -f "$ROOT/$f"; done
command -v psql >/dev/null
command -v python3 >/dev/null
command -v curl >/dev/null
grep -q "def _read_json_body(self):" "$PKG_DIR/backend/api/server.py"
if grep -Rqs "CREATE TABLE.*operation_queue\|CREATE TABLE IF NOT EXISTS.*operation_queue" "$ROOT/backend/db/migrations"; then
  echo "Operations Queue integration: available"
else
  echo "Operations Queue integration: deferred (compatible mode)"
fi
echo "Package 045 doctor PASS"
