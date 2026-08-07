#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
for f in \
  backend/api/server.py \
  backend/db/repositories/asset_repository.py \
  backend/db/migrations/038_cmdb_operational_profile.sql \
  frontend/cmdb-object.html \
  frontend/js/cmdb-object.js \
  frontend/js/graph.js; do
  test -f "$PKG_DIR/payload/$f" || { echo "FAIL: payload/$f"; exit 1; }
  echo "PASS: payload/$f"
done
test -d "$REPO/backend" && test -d "$REPO/frontend" || { echo "FAIL: Nexus repository"; exit 1; }
command -v python3 >/dev/null
command -v psql >/dev/null
python3 -m py_compile \
  "$PKG_DIR/payload/backend/api/server.py" \
  "$PKG_DIR/payload/backend/db/repositories/asset_repository.py" \
  "$PKG_DIR/payload/backend/db/repositories/operational_profile_repository.py" \
  "$PKG_DIR/payload/backend/services/operational_profile_service.py" \
  "$PKG_DIR/payload/backend/services/cmdb_object_service.py"
if command -v node >/dev/null; then
  node --check "$PKG_DIR/payload/frontend/js/cmdb-object.js"
  node --check "$PKG_DIR/payload/frontend/js/graph.js"
fi
echo "Doctor PASS"
