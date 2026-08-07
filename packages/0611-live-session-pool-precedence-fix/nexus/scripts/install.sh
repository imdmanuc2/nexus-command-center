#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../../../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backups/package-0611-$STAMP"
FILES=(
  backend/services/seymour_pool_sync_service.py
  backend/db/repositories/worker_repository.py
  backend/services/operational_state_engine.py
  frontend/js/graph.js
)
for file in "${FILES[@]}"; do
  if [[ -f "$ROOT/$file" ]]; then
    mkdir -p "$BACKUP/$(dirname "$file")"
    cp -a "$ROOT/$file" "$BACKUP/$file"
  fi
done
cp -a "$PKG/payload/." "$ROOT/"
sudo systemctl restart nexus-api.service
echo "Backup: $BACKUP"
echo "Install PASS"
