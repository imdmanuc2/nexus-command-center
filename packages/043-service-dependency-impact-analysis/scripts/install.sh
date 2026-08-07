#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/packages/backups/043-service-dependency-impact-analysis-$STAMP"
mkdir -p "$BACKUP" "$ROOT/backend/db/repositories" "$ROOT/backend/services" "$ROOT/backend/modules" "$ROOT/frontend/css" "$ROOT/frontend/js"
for f in backend/api/server.py frontend/service-operations.html frontend/css/service-operations.css frontend/js/service-operations.js; do test -f "$ROOT/$f" && { mkdir -p "$BACKUP/$(dirname "$f")"; cp "$ROOT/$f" "$BACKUP/$f"; }; done
cp "$PKG_DIR/backend/db/migrations/032_service_dependency_impact_analysis.sql" "$ROOT/backend/db/migrations/"
cp "$PKG_DIR/backend/db/repositories/service_impact_repository.py" "$ROOT/backend/db/repositories/"
cp "$PKG_DIR/backend/services/service_impact_service.py" "$ROOT/backend/services/"
cp "$PKG_DIR/backend/modules/platform_service_impact.py" "$ROOT/backend/modules/"
cp "$PKG_DIR/backend/api/server.py" "$ROOT/backend/api/server.py"
cp "$PKG_DIR/frontend/service-operations.html" "$ROOT/frontend/"
cp "$PKG_DIR/frontend/css/service-operations.css" "$ROOT/frontend/css/"
cp "$PKG_DIR/frontend/js/service-operations.js" "$ROOT/frontend/js/"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f "$ROOT/backend/db/migrations/032_service_dependency_impact_analysis.sql"
python3 -m py_compile "$ROOT/backend/db/repositories/service_impact_repository.py" "$ROOT/backend/services/service_impact_service.py" "$ROOT/backend/modules/platform_service_impact.py" "$ROOT/backend/api/server.py"
sudo systemctl restart nexus-api.service
for _ in {1..20}; do curl -fsS http://127.0.0.1:8080/api/health >/dev/null 2>&1 && break; sleep 1; done
echo "Package 043 installed."
echo "Backup: $BACKUP"
