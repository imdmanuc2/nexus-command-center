#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$(cat "$PACKAGE_ROOT/.last_backup_dir")"
cd "$PROJECT_ROOT"
cp "$BACKUP_DIR/miningcore_repository.py" backend/db/repositories/miningcore_repository.py
cp "$BACKUP_DIR/miningcore_sync_service.py" backend/services/miningcore_sync_service.py
sudo systemctl restart nexus-api.service
echo "Package 012 rollback complete."
