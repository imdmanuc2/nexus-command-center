#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$PACKAGE_ROOT/.last_backup_dir"

test -f "$STATE" || {
  echo "No Package 015 backup state found."
  exit 1
}

BACKUP_DIR="$(cat "$STATE")"
cd "$PROJECT_ROOT"

cp "$BACKUP_DIR/server.py" backend/api/server.py
cp "$BACKUP_DIR/platform_sync_job.py" backend/jobs/platform_sync_job.py

sudo systemctl restart nexus-api.service

echo "Package 015 rollback complete."
echo "Context snapshot tables were preserved."
