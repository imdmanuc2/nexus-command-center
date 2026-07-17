#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/018-operations-timeline-$STAMP"
cd "$ROOT"
mkdir -p "$BACKUP"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"
cp backend/api/server.py "$BACKUP/server.py"
cp backend/jobs/platform_sync_job.py "$BACKUP/platform_sync_job.py"
cp -r "$PKG/backend/"* backend/
set -a; source backend/data/private/cmdb.env; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 \
 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" \
 -d "$NEXUS_DB_NAME" -f backend/db/migrations/012_operations_timeline.sql
python3 "$PKG/scripts/patch_server.py"
python3 "$PKG/scripts/patch_platform_sync.py"
python3 -m py_compile \
 backend/db/repositories/timeline_repository.py \
 backend/services/timeline_service.py \
 backend/modules/platform_timeline.py \
 backend/jobs/platform_timeline_job.py \
 backend/jobs/platform_sync_job.py backend/api/server.py
sudo systemctl restart nexus-api.service
sleep 2
python3 -m backend.jobs.platform_timeline_job
echo "Package 018 installed."
echo "Backup: $BACKUP"
