#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/012-platform-resource-persistence-$STAMP"
cd "$PROJECT_ROOT"
mkdir -p "$BACKUP_DIR"
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"
cp backend/db/repositories/miningcore_repository.py "$BACKUP_DIR/"
cp backend/services/miningcore_sync_service.py "$BACKUP_DIR/"
install -m 0644 "$PACKAGE_ROOT/backend/db/repositories/miningcore_repository.py" backend/db/repositories/miningcore_repository.py
install -m 0644 "$PACKAGE_ROOT/backend/services/miningcore_sync_service.py" backend/services/miningcore_sync_service.py
python3 -m py_compile backend/db/repositories/miningcore_repository.py backend/services/miningcore_sync_service.py backend/jobs/platform_resource_sync.py backend/jobs/platform_sync_job.py
sudo systemctl restart nexus-api.service
sleep 2
python3 -m backend.jobs.platform_resource_sync
echo "Package 012 installed."
echo "Backup: $BACKUP_DIR"
