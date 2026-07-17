#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

echo "== Resource sync =="
python3 -m backend.jobs.platform_resource_sync

echo
echo "== Database counts =="
set -a
source backend/data/private/cmdb.env
set +a

PGPASSWORD="$NEXUS_DB_PASSWORD" \
psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -c "
SELECT COUNT(*) AS blockchain_nodes
FROM nexus.blockchain_nodes;

SELECT COUNT(*) AS miningcore_instances
FROM nexus.miningcore_instances;

SELECT
    instance_id,
    name,
    api_base_url,
    connected,
    api_online,
    status,
    health,
    pool_count
FROM nexus.miningcore_instances
ORDER BY name;
"

echo
echo "== Platform APIs =="

curl -fsS \
  http://127.0.0.1:8080/api/platform/nodes \
  | jq '{status, source, count}'

curl -fsS \
  http://127.0.0.1:8080/api/platform/miningcore \
  | jq '{status, source, count, connectedCount}'

echo
echo "== Integrated one-minute sync =="

python3 - <<'PY'
import contextlib
import io
import json

from backend.jobs.platform_sync_job import run_once

captured_stdout = io.StringIO()

with contextlib.redirect_stdout(captured_stdout):
    result = run_once(
        stale_seconds=300,
        dry_run=False,
    )

summary = {
    "status": result.get("status"),
    "blockchain": (
        result.get("resourcePersistence", {})
        .get("blockchain", {})
        .get("written")
    ),
    "miningcore": (
        result.get("resourcePersistence", {})
        .get("miningcore", {})
        .get("written")
    ),
}

print(json.dumps(summary, indent=2))
PY

echo
echo "Package 012 verified."
