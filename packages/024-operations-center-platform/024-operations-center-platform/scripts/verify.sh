#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

echo "== Operations Center snapshot =="
python3 -m backend.jobs.operations_center_snapshot_job \
  | jq '{
      status,
      source,
      overall,
      infrastructure,
      operations: .operations.summary,
      snapshotsPruned
    }'

echo
echo "== Operations Center APIs =="

for endpoint in \
  api/platform/operations-center \
  api/platform/operations-center/status \
  api/platform/operations-center/queue \
  api/platform/operations-center/snapshot
do
  printf '%-52s ' "/$endpoint"
  curl --max-time 10 -fsS \
    "http://127.0.0.1:8080/$endpoint" \
    >/tmp/package-024-response.json
  jq -e '.status == "ok"' \
    /tmp/package-024-response.json \
    >/dev/null
  echo PASS
done

echo
echo "== Dashboard integrity =="

curl -fsS \
  http://127.0.0.1:8080/api/platform/operations-center \
  >/tmp/package-024-dashboard.json

jq '{
    status,
    source,
    overall,
    infrastructure: {
      workers: .infrastructure.workers,
      topology: .infrastructure.topology,
      workerCountMatchesTopology:
        .infrastructure.workerCountMatchesTopology
    },
    alerts: .alerts.summary,
    recommendations: .recommendations.summary,
    operations: .operations.summary,
    timeline: .timeline.summary
  }' /tmp/package-024-dashboard.json

jq -e '
  .status == "ok"
  and (.overall.healthScore >= 0)
  and (.overall.healthScore <= 100)
  and (
    .infrastructure.workerCountMatchesTopology
    == true
  )
' /tmp/package-024-dashboard.json \
  >/dev/null

echo
echo "== Integrated Platform sync =="

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

operations_center = (
    result.get("operationsCenter")
    or {}
)

print(json.dumps({
    "status": result.get("status"),
    "operationsCenter": {
        "status":
            operations_center.get("status"),
        "overall":
            operations_center.get("overall"),
        "workerCountMatchesTopology":
            (
                operations_center
                .get("infrastructure", {})
                .get("workerCountMatchesTopology")
            ),
    },
}, indent=2))

if operations_center.get("status") != "ok":
    raise SystemExit(
        "Integrated Operations Center failed."
    )
PY

echo
echo "== PostgreSQL snapshots =="

set -a
source backend/data/private/cmdb.env
set +a

PGPASSWORD="$NEXUS_DB_PASSWORD" \
psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -P pager=off \
  -c "
SELECT
    snapshot_key,
    overall_status,
    health_score,
    generated_at
FROM nexus.operations_center_snapshots
ORDER BY generated_at DESC
LIMIT 5;
"

echo "Package 024 verified."
