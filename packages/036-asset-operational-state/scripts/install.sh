#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"
mkdir -p backups/package-036
for f in backend/api/server.py; do [ ! -f "$f" ] || cp -a "$f" "backups/package-036/$(basename "$f").before-036"; done
cp -a "$PKG/backend/." backend/
cp -a "$PKG/frontend/." frontend/
set -a
[ ! -f backend/data/private/cmdb.env ] || source backend/data/private/cmdb.env
set +a
: "${NEXUS_DB_HOST:?NEXUS_DB_HOST is required}"
: "${NEXUS_DB_PORT:?NEXUS_DB_PORT is required}"
: "${NEXUS_DB_NAME:?NEXUS_DB_NAME is required}"
: "${NEXUS_DB_USER:?NEXUS_DB_USER is required}"
: "${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD is required}"
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f backend/db/migrations/025_asset_operational_state.sql
sudo systemctl restart nexus-api.service 2>/dev/null || true
echo "Package 036 installed."
