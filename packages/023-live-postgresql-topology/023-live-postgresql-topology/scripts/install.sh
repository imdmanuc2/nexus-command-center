#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/023-live-postgresql-topology-$STAMP"

cd "$ROOT"
mkdir -p "$BACKUP"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"

for file in \
  backend/db/repositories/relationship_repository.py \
  backend/services/topology_service.py \
  backend/jobs/platform_sync_job.py \
  frontend/js/nexus-platform-explorer.js
do
  mkdir -p "$BACKUP/$(dirname "$file")"
  cp "$file" "$BACKUP/$file"
done

cp -r "$PKG/backend/"* backend/
cp -r "$PKG/frontend/"* frontend/

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
  -f backend/db/migrations/015_live_postgresql_topology.sql

python3 -m py_compile \
  backend/db/repositories/relationship_repository.py \
  backend/db/repositories/topology_repository.py \
  backend/services/topology_reconciliation_service.py \
  backend/services/topology_service.py \
  backend/jobs/topology_reconciliation_job.py \
  backend/jobs/platform_sync_job.py

python3 -m backend.jobs.topology_reconciliation_job

sudo systemctl restart nexus-api.service
sleep 2

echo "Package 023 installed."
echo "Backup: $BACKUP"
