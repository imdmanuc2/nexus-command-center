#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/026-operations-center-controls-$STAMP"
cd "$ROOT"
mkdir -p "$BACKUP/backend/api" "$BACKUP/backend/db/repositories" "$BACKUP/backend/services" "$BACKUP/backend/modules" "$BACKUP/frontend/css" "$BACKUP/frontend/js"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"
for file in backend/api/server.py backend/db/repositories/automation_repository.py backend/services/automation_engine_service.py backend/services/operations_center_service.py backend/modules/platform_automation.py frontend/operations-center.html frontend/css/operations-center.css frontend/js/operations-center.js; do
  cp "$file" "$BACKUP/$file"
done
cp -r "$PKG/backend/"* backend/
cp -r "$PKG/frontend/"* frontend/
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -f backend/db/migrations/017_operations_control_audit.sql
python3 -m py_compile backend/api/server.py backend/db/repositories/automation_repository.py backend/services/automation_engine_service.py backend/services/operations_center_service.py backend/modules/platform_automation.py
sudo systemctl restart nexus-api.service
sleep 3
echo "Package 026 installed."
echo "Backup: $BACKUP"
