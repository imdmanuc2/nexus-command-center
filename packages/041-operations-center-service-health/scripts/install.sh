#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
BACKUP="$ROOT/packages/backups/041-operations-center-service-health-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BACKUP"
for f in backend/api/server.py frontend/js/nav.js; do [[ -f "$ROOT/$f" ]] && cp --parents "$ROOT/$f" "$BACKUP/"; done
for f in backend/db/repositories/service_operations_repository.py backend/services/service_operations_service.py backend/modules/platform_service_operations.py backend/api/server.py frontend/service-operations.html frontend/css/service-operations.css frontend/js/service-operations.js frontend/js/nav.js backend/db/migrations/030_operations_center_service_health.sql; do install -D -m 0644 "$PKG/$f" "$ROOT/$f"; done
PGPASSWORD="${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD missing}" psql -v ON_ERROR_STOP=1 -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -f "$ROOT/backend/db/migrations/030_operations_center_service_health.sql"
sudo systemctl restart nexus-api.service
printf 'Package 041 installed.\nBackup: %s\n' "$BACKUP"
