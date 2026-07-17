#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/025-operations-center-ui-$STAMP"

cd "$ROOT"

mkdir -p \
  "$BACKUP/frontend/js" \
  "$BACKUP/backend/api"

printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"

cp frontend/js/nav.js \
  "$BACKUP/frontend/js/nav.js"

cp backend/api/server.py \
  "$BACKUP/backend/api/server.py"

cp -r "$PKG/frontend/"* frontend/

mkdir -p backend/api

cp \
  "$PKG/backend/api/server.py" \
  backend/api/server.py

sudo systemctl restart nexus-api.service
sleep 2

echo "Package 025 installed."
echo "Backup: $BACKUP"
