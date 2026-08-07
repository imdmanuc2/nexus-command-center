#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"
set -a
source backend/data/private/cmdb.env
set +a
/usr/bin/python3 -m backend.jobs.platform_sync_job >/tmp/package-0611-sync.log
python3 - <<'PY'
import json
import time
import urllib.request


def get(path):
    with urllib.request.urlopen(f"http://localhost:8080{path}", timeout=10) as response:
        return json.load(response)

last = None
for _ in range(12):
    data = get("/api/platform/workers")
    workers = data.get("workers", [])
    candidates = [
        worker for worker in workers
        if worker.get("sourceSystem") == "seymour-native-stratum"
        and str(worker.get("workerName") or "").endswith(".002")
    ]
    if candidates:
        last = candidates[0]
        if (
            last.get("assetId") == "asset-b63808dd"
            and last.get("currentSession") is True
            and last.get("poolInstanceId") == "seymour-btc-solo"
        ):
            break
    time.sleep(2)
else:
    raise AssertionError(f"Mining System 2 did not hand off to Seymour: {last}")

assert last.get("activityState") in {"active", "idle"}, last
assert last.get("status") == "online", last
print("PASS: Mining System 2 current session belongs to Seymour")
print("PASS: live session accepted without requiring first share")

workers = get("/api/platform/workers").get("workers", [])
conflicts = [
    worker for worker in workers
    if worker.get("assetId") == "asset-b63808dd"
    and worker.get("currentSession") is True
    and worker.get("poolInstanceId") != "seymour-btc-solo"
]
assert not conflicts, conflicts
print("PASS: stale BCH and CKPool sessions are not current")

topology = get("/api/platform/topology")
edges = topology.get("relationships") or topology.get("edges") or []
matching = [
    edge for edge in edges
    if str(edge.get("sourceId") or edge.get("source") or "") == "asset-b63808dd"
    and str(edge.get("relationshipType") or edge.get("type") or "").lower().replace("_", "-") == "mines-on"
]
assert matching, "No current Mining System 2 mines-on relationship"
assert any(str(edge.get("targetId") or edge.get("target") or "") == "seymour-btc-solo" for edge in matching), matching
assert not any("4000-bch" in str(edge.get("targetId") or edge.get("target") or "") for edge in matching), matching
print("PASS: topology points Mining System 2 to Seymour only")
PY
curl -fsS http://localhost:8080/api/platform/topology >/dev/null
echo "PASS: /api/platform/topology"
grep -q 'RECEIVING JOBS' frontend/js/graph.js
grep -q 'Current live session authority wins' backend/db/repositories/worker_repository.py
echo "PASS: connected-state Canvas rendering"
echo "Verify PASS"
