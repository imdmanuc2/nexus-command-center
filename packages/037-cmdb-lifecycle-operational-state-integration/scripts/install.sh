#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
mkdir -p "$ROOT/backups/package-037"; ts=$(date +%Y%m%d-%H%M%S)
for f in backend/api/server.py frontend/assets.html frontend/js/assets.js; do [[ -f "$ROOT/$f" ]] && cp "$ROOT/$f" "$ROOT/backups/package-037/$(basename "$f").$ts"; done
cp "$PKG/backend/db/repositories/cmdb_lifecycle_repository.py" "$ROOT/backend/db/repositories/"
cp "$PKG/backend/services/cmdb_lifecycle_service.py" "$ROOT/backend/services/"
cp "$PKG/backend/modules/platform_cmdb_lifecycle.py" "$ROOT/backend/modules/"
cp "$PKG/backend/api/server.py" "$ROOT/backend/api/server.py"
cp "$PKG/frontend/assets.html" "$ROOT/frontend/assets.html"
cp "$PKG/frontend/js/assets.js" "$ROOT/frontend/js/assets.js"
cp "$PKG/frontend/css/cmdb-lifecycle.css" "$ROOT/frontend/css/cmdb-lifecycle.css"
cp "$PKG/backend/db/migrations/026_cmdb_lifecycle_integration.sql" "$ROOT/backend/db/migrations/"
PGPASSWORD="${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD missing}" psql -v ON_ERROR_STOP=1 -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -f "$ROOT/backend/db/migrations/026_cmdb_lifecycle_integration.sql"
sudo systemctl restart nexus-api.service || true
echo "Package 037 installed."
