#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$PKG/.last_backup_dir" || { echo "No Package 028 backup state found."; exit 1; }
BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"
cp "$BACKUP/backend/services/automation_engine_service.py" backend/services/
cp "$BACKUP/backend/executors/registry.py" backend/executors/
rm -rf backend/capabilities backend/transports
rm -f backend/executors/managed_host_executor.py backend/db/migrations/019_managed_host_capabilities.sql backend/data/private/managed_hosts.example.json
sudo systemctl restart nexus-api.service
echo "Package 028 application rollback complete. Migration 019 data retained."
