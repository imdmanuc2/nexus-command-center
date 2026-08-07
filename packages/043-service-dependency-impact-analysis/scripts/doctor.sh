#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
test -f "$ROOT/backend/data/private/cmdb.env" || { echo "cmdb.env missing"; exit 1; }
test -f "$ROOT/backend/api/server.py"
command -v python3 >/dev/null
command -v psql >/dev/null
python3 -m py_compile "$PKG_DIR/backend/db/repositories/service_impact_repository.py" "$PKG_DIR/backend/services/service_impact_service.py" "$PKG_DIR/backend/modules/platform_service_impact.py" "$PKG_DIR/backend/api/server.py"
echo "Package 043 doctor PASS"
