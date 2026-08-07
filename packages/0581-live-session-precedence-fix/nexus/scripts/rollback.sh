#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="$HOME/Projects/Seymour/nexus-command-center"
BACKUP="$(cat "$PKG_DIR/.last_backup_dir")"
cd "$REPO"
cp "$BACKUP/backend/services/seymour_pool_sync_service.py" backend/services/
cp "$BACKUP/backend/db/repositories/worker_repository.py" backend/db/repositories/
cp "$BACKUP/frontend/js/graph.js" frontend/js/
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
