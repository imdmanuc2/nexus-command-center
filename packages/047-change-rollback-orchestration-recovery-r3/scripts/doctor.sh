#!/usr/bin/env bash
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"

test -f "$ROOT/backend/api/server.py"
test -f "$ROOT/backend/data/private/cmdb.env"
command -v python3 >/dev/null
command -v psql >/dev/null
command -v curl >/dev/null
command -v systemctl >/dev/null

grep -q "CREATE TABLE IF NOT EXISTS nexus.change_rollback_plans" "$PKG_DIR/backend/db/migrations/036_change_rollback_orchestration_recovery.sql"
grep -q 'parents\[2\]' "$PKG_DIR/backend/api/install_change_rollback_routes.py"
grep -q "find_routes_dict" "$PKG_DIR/backend/api/install_change_rollback_routes.py"
grep -q "Patched and verified live API file" "$PKG_DIR/backend/api/install_change_rollback_routes.py"

python3 -m py_compile   "$PKG_DIR/backend/api/install_change_rollback_routes.py"   "$PKG_DIR/backend/modules/platform_change_rollback.py"   "$PKG_DIR/backend/services/change_rollback_service.py"   "$PKG_DIR/backend/jobs/change_rollback_worker.py"

echo "Package 047 Revision 3 doctor PASS"
