#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$PKG/.last_backup_dir" || { echo "No Package 026 backup state found."; exit 1; }
BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"
for file in backend/api/server.py backend/db/repositories/automation_repository.py backend/services/automation_engine_service.py backend/services/operations_center_service.py backend/modules/platform_automation.py frontend/operations-center.html frontend/css/operations-center.css frontend/js/operations-center.js; do
  cp "$BACKUP/$file" "$file"
done
sudo systemctl restart nexus-api.service
echo "Package 026 application rollback complete."
echo "Migration 017 audit data was retained intentionally."
