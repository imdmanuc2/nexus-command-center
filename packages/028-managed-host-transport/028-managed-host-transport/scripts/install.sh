#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/028-managed-host-transport-$STAMP"
cd "$ROOT"
mkdir -p "$BACKUP/backend/services" "$BACKUP/backend/executors"
printf '%s
' "$BACKUP" > "$PKG/.last_backup_dir"
cp backend/services/automation_engine_service.py "$BACKUP/backend/services/"
cp backend/executors/registry.py "$BACKUP/backend/executors/"
cp -r "$PKG/backend/"* backend/
set -a; source backend/data/private/cmdb.env; set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -f backend/db/migrations/019_managed_host_capabilities.sql
python3 -m py_compile backend/capabilities/*.py backend/transports/*.py backend/executors/managed_host_executor.py backend/executors/registry.py backend/services/automation_engine_service.py
sudo systemctl restart nexus-api.service
sleep 3
echo "Package 028 installed."
echo "Backup: $BACKUP"
