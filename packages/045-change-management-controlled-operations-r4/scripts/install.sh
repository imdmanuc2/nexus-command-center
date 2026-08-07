#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/packages/backups/045-change-management-controlled-operations-$STAMP"
mkdir -p "$BACKUP" "$ROOT/backend/db/repositories" "$ROOT/backend/services" "$ROOT/backend/modules"
for f in backend/api/server.py frontend/service-operations.html frontend/css/service-operations.css frontend/js/service-operations.js; do
  if test -f "$ROOT/$f"; then mkdir -p "$BACKUP/$(dirname "$f")"; cp "$ROOT/$f" "$BACKUP/$f"; fi
done
cp "$PKG_DIR/backend/db/migrations/034_change_management_controlled_operations.sql" "$ROOT/backend/db/migrations/"
cp "$PKG_DIR/backend/db/repositories/change_management_repository.py" "$ROOT/backend/db/repositories/"
cp "$PKG_DIR/backend/services/change_management_service.py" "$ROOT/backend/services/"
cp "$PKG_DIR/backend/modules/platform_change_management.py" "$ROOT/backend/modules/"
cp "$PKG_DIR/backend/api/server.py" "$ROOT/backend/api/server.py"
cp "$PKG_DIR/frontend/service-operations.html" "$ROOT/frontend/"
cp "$PKG_DIR/frontend/css/service-operations.css" "$ROOT/frontend/css/"
cp "$PKG_DIR/frontend/js/service-operations.js" "$ROOT/frontend/js/"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f "$ROOT/backend/db/migrations/034_change_management_controlled_operations.sql"
python3 -m py_compile "$ROOT/backend/db/repositories/change_management_repository.py" "$ROOT/backend/services/change_management_service.py" "$ROOT/backend/modules/platform_change_management.py" "$ROOT/backend/api/server.py"
sudo systemctl restart nexus-api.service
for _ in {1..20}; do curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:8080/api/health >/dev/null
echo "Package 045 installed."
echo "Backup: $BACKUP"
