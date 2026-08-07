#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="$HOME/Projects/Seymour/nexus-command-center"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO/backups/package-0581-$STAMP"
mkdir -p "$BACKUP/backend/services" "$BACKUP/backend/db/repositories" "$BACKUP/frontend/js"
cd "$REPO"
cp backend/services/seymour_pool_sync_service.py "$BACKUP/backend/services/"
cp backend/db/repositories/worker_repository.py "$BACKUP/backend/db/repositories/"
cp frontend/js/graph.js "$BACKUP/frontend/js/"
cp "$PKG_DIR/payload/backend/services/seymour_pool_sync_service.py" backend/services/
cp "$PKG_DIR/payload/backend/db/repositories/worker_repository.py" backend/db/repositories/
cp "$PKG_DIR/payload/frontend/js/graph.js" frontend/js/
python3 -m py_compile backend/services/seymour_pool_sync_service.py backend/db/repositories/worker_repository.py
sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service
echo "$BACKUP" > "$PKG_DIR/.last_backup_dir"
echo "Backup: $BACKUP"
echo "Install PASS"
