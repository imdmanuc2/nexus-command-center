#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; cd "$ROOT"
set -a; source backend/data/private/cmdb.env; set +a
BACKUP="backups/package-035-remote-deployment-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BACKUP"
for f in backend/api/server.py; do [ -f "$f" ] && cp --parents "$f" "$BACKUP"; done
cp -a "$PKG/backend/." backend/
cp -a "$PKG/frontend/." frontend/
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f backend/db/migrations/024_remote_deployments.sql
if command -v systemctl >/dev/null && systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then sudo systemctl restart nexus-api.service; fi
echo "$BACKUP" > "$PKG/.last-backup"
echo "Package 035 installed."
