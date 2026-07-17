#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

echo "== Topology reconciliation =="
python3 -m backend.jobs.topology_reconciliation_job

echo
echo "== Integrated Platform sync =="
python3 - <<'PY'
import contextlib
import io
import json

from backend.jobs.platform_sync_job import run_once

captured = io.StringIO()

with contextlib.redirect_stdout(captured):
    result = run_once(stale_seconds=300, dry_run=False)

print(json.dumps({
    "status": result.get("status"),
    "workerActivityReconciliation":
        result.get("workerActivityReconciliation"),
    "topologyReconciliation":
        result.get("topologyReconciliation"),
    "eventEngine": result.get("eventEngine"),
    "timelineEngine": result.get("timelineEngine"),
}, indent=2))
PY

echo
echo "== Topology API integrity =="

curl -fsS http://127.0.0.1:8080/api/platform/topology \
  >/tmp/nexus-package-023-topology.json

jq '{
    status,
    source,
    counts,
    assetPoolEdges: [
      .edges[]
      | select(
          .type == "mines-on"
          and (
              .properties.relationshipSource
              == "platform-topology-reconciliation"
          )
      )
      | {
          source,
          target,
          worker: .properties.canonicalWorkerId
        }
    ],
    poolNodeEdges: [
      .edges[]
      | select(.type == "backed-by")
      | {
          source,
          target,
          coin: .properties.coin
        }
    ]
  }' /tmp/nexus-package-023-topology.json

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(
    Path("/tmp/nexus-package-023-topology.json").read_text()
)

nodes = payload.get("nodes") or []
edges = payload.get("edges") or []
node_ids = [node["id"] for node in nodes]

duplicates = sorted({
    node_id
    for node_id in node_ids
    if node_ids.count(node_id) > 1
})

node_set = set(node_ids)
orphans = [
    edge
    for edge in edges
    if edge["source"] not in node_set
    or edge["target"] not in node_set
]

edge_keys = [
    (
        edge["source"],
        edge["target"],
        edge["type"],
    )
    for edge in edges
]

duplicate_edges = sorted({
    key
    for key in edge_keys
    if edge_keys.count(key) > 1
})

counts = payload.get("counts") or {}
active_assets = int(counts.get("activePhysicalAssets") or 0)
worker_nodes = int(counts.get("workerNodes") or 0)

result = {
    "duplicateNodeIds": duplicates,
    "orphanEdges": len(orphans),
    "duplicateEdges": [
        list(key)
        for key in duplicate_edges
    ],
    "activePhysicalAssets": active_assets,
    "standaloneWorkerNodes": worker_nodes,
}

print(json.dumps(result, indent=2))

if duplicates or orphans or duplicate_edges:
    raise SystemExit("Topology integrity validation failed.")
PY

echo
echo "== PostgreSQL topology relationships =="

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
    source_type,
    source_id,
    relationship_type,
    target_type,
    target_id,
    status,
    metadata
FROM nexus.relationships
WHERE source = 'platform-topology-reconciliation'
ORDER BY
    source_type,
    source_id,
    relationship_type,
    target_id;
"

echo "Package 023 verified."
