#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
python3 -m backend.jobs.platform_resource_sync
set -a; source backend/data/private/cmdb.env; set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "SELECT COUNT(*) AS blockchain_nodes FROM nexus.blockchain_nodes; SELECT COUNT(*) AS miningcore_instances FROM nexus.miningcore_instances;"
curl -fsS http://127.0.0.1:8080/api/platform/nodes | jq '{status,source,count}'
curl -fsS http://127.0.0.1:8080/api/platform/miningcore | jq '{status,source,count,connectedCount}'
python3 -m backend.jobs.platform_sync_job --stale-seconds 300
echo 'Platform resource persistence verified.'
