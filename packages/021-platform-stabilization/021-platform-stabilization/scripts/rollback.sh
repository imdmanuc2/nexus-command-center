#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$PKG/.last_backup_dir" || { echo "No Package 021 backup state found."; exit 1; }
BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"
cp "$BACKUP/alert_repository.py" backend/db/repositories/alert_repository.py
cp "$BACKUP/platform_event_repository.py" backend/db/repositories/platform_event_repository.py
cp "$BACKUP/context_repository.py" backend/db/repositories/context_repository.py
sudo systemctl restart nexus-api.service
echo "Package 021 rollback complete."
