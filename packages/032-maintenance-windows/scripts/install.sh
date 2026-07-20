#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; cd "$ROOT"
set -a; source backend/data/private/cmdb.env; set +a
BACKUP="backups/package-032-maintenance-windows-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BACKUP"
for f in backend/api/server.py backend/services/alert_engine_service.py; do [ -f "$f" ] && cp --parents "$f" "$BACKUP"; done
cp -a "$PKG/backend/." backend/
cp -a "$PKG/frontend/." frontend/
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f backend/db/migrations/023_maintenance_windows.sql
if command -v systemctl >/dev/null && systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then sudo systemctl restart nexus-api.service; fi
echo "$BACKUP" > "$PKG/.last-backup"
echo "Package 032 installed."
