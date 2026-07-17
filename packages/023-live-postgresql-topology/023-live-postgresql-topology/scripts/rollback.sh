#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

test -f "$PKG/.last_backup_dir" || {
  echo "No Package 023 backup state found."
  exit 1
}

BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"

for file in \
  backend/db/repositories/relationship_repository.py \
  backend/services/topology_service.py \
  backend/jobs/platform_sync_job.py \
  frontend/js/nexus-platform-explorer.js
do
  cp "$BACKUP/$file" "$file"
done

sudo systemctl restart nexus-api.service

echo "Package 023 rollback complete."
echo "Topology relationship history was preserved."
