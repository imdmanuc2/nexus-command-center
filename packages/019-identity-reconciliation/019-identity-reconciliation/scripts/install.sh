#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}";PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)";STAMP="$(date +%Y%m%d-%H%M%S)";BACKUP="$ROOT/backend/data/private/package-backups/019-identity-reconciliation-$STAMP"
cd "$ROOT";mkdir -p "$BACKUP";printf '%s
' "$BACKUP" > "$PKG/.last_backup_dir";cp backend/db/repositories/worker_repository.py "$BACKUP/worker_repository.py";cp -r "$PKG/backend/"* backend/
set -a;source backend/data/private/cmdb.env;set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f backend/db/migrations/013_identity_reconciliation.sql
python3 -m py_compile backend/db/repositories/identity_reconciliation_repository.py backend/db/repositories/worker_repository.py backend/services/identity_reconciliation_service.py backend/jobs/identity_reconciliation_job.py
python3 -m backend.jobs.identity_reconciliation_job
echo "Package 019 installed.";echo "Backup: $BACKUP"
