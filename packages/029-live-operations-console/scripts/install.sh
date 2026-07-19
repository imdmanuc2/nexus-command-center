#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/029-live-operations-console-$STAMP"
cd "$ROOT"
mkdir -p "$BACKUP/backend/services" "$BACKUP/backend/api" "$BACKUP/frontend/js" "$BACKUP/frontend/css" "$BACKUP/frontend"
printf '%s
' "$BACKUP" > "$PKG/.last_backup_dir"
for f in backend/services/automation_engine_service.py backend/api/server.py frontend/operations-center.html frontend/js/operations-center.js frontend/css/operations-center.css; do mkdir -p "$BACKUP/$(dirname "$f")"; cp "$f" "$BACKUP/$f"; done
cp -r "$PKG/backend/"* backend/
cp -r "$PKG/frontend/"* frontend/
set -a; source backend/data/private/cmdb.env; set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -f backend/db/migrations/020_live_operations_console.sql
python3 -m py_compile backend/db/repositories/operation_session_repository.py backend/services/operation_session_service.py backend/services/automation_engine_service.py backend/modules/platform_operation_sessions.py backend/api/server.py
sudo systemctl restart nexus-api.service
sleep 3
echo "Package 029 installed."
echo "Backup: $BACKUP"
