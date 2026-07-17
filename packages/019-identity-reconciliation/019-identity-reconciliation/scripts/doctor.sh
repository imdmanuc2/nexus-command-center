#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}";cd "$ROOT"
test -f backend/data/private/cmdb.env
test -f backend/db/repositories/worker_repository.py
set -a;source backend/data/private/cmdb.env;set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -At -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname='nexus' AND tablename='workers' AND indexname='uq_workers_source_identity';" | grep -qx 1
echo "Package 019 doctor passed."
