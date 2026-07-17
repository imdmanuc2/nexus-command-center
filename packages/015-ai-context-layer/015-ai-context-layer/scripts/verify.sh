#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

echo "== Context builder =="
python3 -m backend.jobs.platform_context_job

echo "== Database snapshots =="
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
SELECT
    context_key,
    context_version,
    generated_at
FROM nexus.platform_context_snapshots
ORDER BY context_key;
"

echo "== Context APIs =="
for endpoint in \
  context \
  context/home \
  context/mining \
  context/infrastructure \
  context/health
do
  curl -fsS \
    "http://127.0.0.1:8080/api/platform/$endpoint" \
    | jq '{
        status,
        source,
        contextKey,
        generatedAt
      }'
done

echo "== Home context summary =="
curl -fsS \
  http://127.0.0.1:8080/api/platform/context/home \
  | jq '{
      fleetHealth: .context.fleetHealth,
      workers: .context.workers.total,
      pools: .context.pools.total,
      nodes: .context.nodes.total,
      miningcore: .context.miningcore.total,
      alerts: (.context.alerts | length),
      recentEvents: (.context.recentEvents | length)
    }'

echo "== Integrated sync =="
python3 - <<'PY'
import contextlib
import io
import json

from backend.jobs.platform_sync_job import run_once

captured = io.StringIO()

with contextlib.redirect_stdout(captured):
    result = run_once(
        stale_seconds=300,
        dry_run=False,
    )

print(json.dumps({
    "status": result.get("status"),
    "contextBuilder": result.get("contextBuilder"),
}, indent=2))
PY

echo "Package 015 verified."
