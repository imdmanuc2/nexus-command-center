#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$ROOT/backend/capabilities/registry.py"
test -f "$ROOT/backend/transports/registry.py"
test -f "$ROOT/backend/data/private/cmdb.env"
command -v psql >/dev/null
command -v python3 >/dev/null
command -v curl >/dev/null
grep -q "CREATE TABLE IF NOT EXISTS nexus.operation_queue" "$PKG_DIR/backend/db/migrations/035_change_execution_worker_reconciliation.sql"
grep -q "FOR UPDATE SKIP LOCKED" "$PKG_DIR/backend/db/repositories/change_execution_repository.py"
grep -q 'json_response({"status":"error","error":str(exc)}, 400)' "$PKG_DIR/backend/api/server.py"
python3 -m py_compile \
  "$PKG_DIR/backend/api/server.py" \
  "$PKG_DIR/backend/db/repositories/change_execution_repository.py" \
  "$PKG_DIR/backend/services/change_execution_service.py" \
  "$PKG_DIR/backend/jobs/change_execution_worker.py"
echo "Operations Queue integration: available"
echo "Managed Host capability registry: available"
echo "Package 046 doctor PASS"
