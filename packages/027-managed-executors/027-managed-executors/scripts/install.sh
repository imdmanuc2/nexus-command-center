#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/027-managed-executors-$STAMP"

cd "$ROOT"
mkdir -p "$BACKUP/backend/services"
cp backend/services/automation_engine_service.py \
  "$BACKUP/backend/services/automation_engine_service.py"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"

mkdir -p backend/executors backend/db/migrations backend/services
cp -r "$PKG/backend/executors/"* backend/executors/
cp "$PKG/backend/services/automation_engine_service.py" \
  backend/services/automation_engine_service.py
cp "$PKG/backend/db/migrations/018_managed_executor_actions.sql" \
  backend/db/migrations/018_managed_executor_actions.sql

set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"

psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f backend/db/migrations/018_managed_executor_actions.sql

python3 -m py_compile \
  backend/executors/*.py \
  backend/services/automation_engine_service.py

sudo systemctl restart nexus-api.service
sleep 3

echo "Package 027 installed."
echo "Backup: $BACKUP"
