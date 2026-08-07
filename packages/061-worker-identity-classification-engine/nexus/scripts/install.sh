#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../../../.." && pwd)"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$ROOT/backups/package-061-$STAMP"
mkdir -p "$BACKUP/backend/services" "$BACKUP/backend/data/config" "$BACKUP/frontend/js"
for f in backend/services/seymour_pool_sync_service.py backend/data/config/seymour_pool_engine.json frontend/js/graph.js; do [[ -f "$ROOT/$f" ]] && cp "$ROOT/$f" "$BACKUP/$f"; done
cp -a "$PKG/payload/." "$ROOT/"
sudo systemctl restart nexus-api.service
echo "Backup: $BACKUP"
echo "Install PASS"
