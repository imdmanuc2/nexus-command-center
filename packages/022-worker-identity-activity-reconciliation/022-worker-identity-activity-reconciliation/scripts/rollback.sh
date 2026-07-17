#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$PKG/.last_backup_dir" || {
  echo "No Package 022 backup state found."
  exit 1
}

BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"

for file in \
  backend/db/repositories/worker_repository.py \
  backend/services/worker_service.py \
  backend/services/fleet_service.py \
  backend/services/platform_context_service.py \
  backend/services/recommendation_engine_service.py \
  backend/services/topology_service.py \
  backend/services/generic_stratum_sync_service.py \
  backend/jobs/platform_sync_job.py
do
  cp "$BACKUP/$file" "$file"
done

sudo systemctl restart nexus-api.service

echo "Package 022 rollback complete."
echo "Database activity columns were preserved."
