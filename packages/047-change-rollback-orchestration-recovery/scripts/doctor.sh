#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; ROOT="$(cd "$PKG_DIR/../.." && pwd)"
test -f "$ROOT/backend/data/private/cmdb.env"; test -f "$ROOT/backend/api/server.py"; test -f "$ROOT/backend/db/repositories/change_execution_repository.py"
grep -q platform_change_execution "$ROOT/backend/api/server.py"
python3 -m py_compile "$PKG_DIR"/backend/db/repositories/change_rollback_repository.py "$PKG_DIR"/backend/services/change_rollback_service.py "$PKG_DIR"/backend/modules/platform_change_rollback.py "$PKG_DIR"/backend/jobs/change_rollback_worker.py "$PKG_DIR"/backend/api/install_change_rollback_routes.py
echo 'Package 047 doctor PASS'
