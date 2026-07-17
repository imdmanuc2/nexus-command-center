#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/024-operations-center-platform-$STAMP"

cd "$ROOT"

mkdir -p "$BACKUP"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"

cp backend/api/server.py \
  "$BACKUP/server.py"

cp backend/jobs/platform_sync_job.py \
  "$BACKUP/platform_sync_job.py"

cp -r "$PKG/backend/"* backend/

set -a
source backend/data/private/cmdb.env
set +a

PGPASSWORD="$NEXUS_DB_PASSWORD" \
psql \
  -v ON_ERROR_STOP=1 \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -f backend/db/migrations/016_operations_center_platform.sql

python3 "$PKG/scripts/patch_server.py"
python3 "$PKG/scripts/patch_platform_sync.py"

python3 -m py_compile \
  backend/db/repositories/operations_center_repository.py \
  backend/services/operations_center_service.py \
  backend/modules/platform_operations_center.py \
  backend/jobs/operations_center_snapshot_job.py \
  backend/jobs/platform_sync_job.py \
  backend/api/server.py

python3 -m backend.jobs.operations_center_snapshot_job \
  >/tmp/package-024-snapshot.json

sudo systemctl restart nexus-api.service
sleep 2

echo "Package 024 installed."
echo "Backup: $BACKUP"
