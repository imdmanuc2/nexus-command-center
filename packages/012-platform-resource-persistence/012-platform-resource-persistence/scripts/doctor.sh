#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"
test -f backend/jobs/platform_resource_sync.py
set -a
source backend/data/private/cmdb.env
set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -At -c "
SELECT COUNT(*) FROM information_schema.columns
WHERE table_schema='nexus' AND table_name='miningcore_instances'
AND column_name IN ('api_base_url','console_url','software_version','api_online','observed_state','metadata','endpoint','connected','raw_payload');" | grep -qx 9
curl -fsS http://127.0.0.1:8080/api/connectors/status | jq -e '.connectors.miningcore.instances | length > 0' >/dev/null
echo "Package 012 doctor passed."
