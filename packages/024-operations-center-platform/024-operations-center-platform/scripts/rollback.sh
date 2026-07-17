#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

test -f "$PKG/.last_backup_dir" || {
  echo "No Package 024 backup state found."
  exit 1
}

BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"

cp "$BACKUP/server.py" \
  backend/api/server.py

cp "$BACKUP/platform_sync_job.py" \
  backend/jobs/platform_sync_job.py

sudo systemctl restart nexus-api.service

echo "Package 024 rollback complete."
echo "Operations Center snapshots were preserved."
