#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/022-worker-identity-activity-$STAMP"

cd "$ROOT"
mkdir -p "$BACKUP"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"

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
  mkdir -p "$BACKUP/$(dirname "$file")"
  cp "$file" "$BACKUP/$file"
done

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
  -f backend/db/migrations/014_worker_identity_activity_reconciliation.sql

python3 -m py_compile \
  backend/db/repositories/worker_repository.py \
  backend/services/worker_service.py \
  backend/services/fleet_service.py \
  backend/services/platform_context_service.py \
  backend/services/recommendation_engine_service.py \
  backend/services/topology_service.py \
  backend/services/generic_stratum_sync_service.py \
  backend/services/worker_activity_reconciliation_service.py \
  backend/jobs/worker_activity_reconciliation_job.py \
  backend/jobs/platform_sync_job.py

python3 -m backend.jobs.worker_activity_reconciliation_job

sudo systemctl restart nexus-api.service
sleep 2

echo "Package 022 installed."
echo "Backup: $BACKUP"
