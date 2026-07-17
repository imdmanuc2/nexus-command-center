#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/016-recommendation-engine-$STAMP"

cd "$PROJECT_ROOT"
mkdir -p "$BACKUP_DIR"
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"

cp backend/api/server.py "$BACKUP_DIR/server.py"
cp backend/jobs/platform_sync_job.py "$BACKUP_DIR/platform_sync_job.py"

cp -r "$PACKAGE_ROOT/backend/"* backend/

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
  -f backend/db/migrations/010_recommendation_engine.sql

python3 "$PACKAGE_ROOT/scripts/patch_server.py"
python3 "$PACKAGE_ROOT/scripts/patch_platform_sync.py"

python3 -m py_compile \
  backend/db/repositories/recommendation_repository.py \
  backend/services/recommendation_rules/base.py \
  backend/services/recommendation_rules/worker_rules.py \
  backend/services/recommendation_rules/node_rules.py \
  backend/services/recommendation_rules/miningcore_rules.py \
  backend/services/recommendation_rules/alert_rules.py \
  backend/services/recommendation_engine_service.py \
  backend/modules/platform_recommendations.py \
  backend/jobs/platform_recommendation_job.py \
  backend/jobs/platform_sync_job.py \
  backend/api/server.py

sudo systemctl restart nexus-api.service
sleep 2

python3 -m backend.jobs.platform_recommendation_job

echo "Package 016 installed."
echo "Backup: $BACKUP_DIR"
