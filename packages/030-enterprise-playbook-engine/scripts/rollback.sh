#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; cd "$ROOT"; set -a; source backend/data/private/cmdb.env; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" <<'SQL'
BEGIN; DROP TABLE IF EXISTS nexus.playbook_steps; DROP TABLE IF EXISTS nexus.playbook_runs; DROP TABLE IF EXISTS nexus.playbook_versions; DROP TABLE IF EXISTS nexus.playbooks; COMMIT;
SQL
echo "Database objects removed. Restore source files from Git to complete rollback."
