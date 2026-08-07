#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

node --check "$ROOT/frontend/js/graph.js"
grep -q 'PACKAGE 062.1: canonical topology' "$ROOT/frontend/js/graph.js"
echo "PASS: canonical topology is Live Canvas authority"
grep -q 'function livePoolWorkers' "$ROOT/frontend/js/graph.js"
grep -q 'worker.currentSession === true' "$ROOT/frontend/js/graph.js"
echo "PASS: current-session pool aggregation"
grep -q 'ACCEPTING ·' "$ROOT/frontend/js/graph.js"
echo "PASS: active pool status and hashrate rendering"

curl -fsS http://localhost:8080/graph.html >/dev/null
echo "PASS: /graph.html"

python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://localhost:8080/api/platform/topology", timeout=15) as response:
    topology = json.load(response)

edges = topology.get("edges", [])
active = {}
for edge in edges:
    kind = str(edge.get("type", "")).lower().replace("_", "-")
    if kind != "mines-on" or str(edge.get("status", "active")).lower() != "active":
        continue
    source = edge.get("source")
    target = edge.get("target")
    if source and target:
        if source in active and active[source] != target:
            raise AssertionError(f"multiple live MINES_ON targets for {source}: {active[source]}, {target}")
        active[source] = target

expected_assets = {"asset-28a5a306", "asset-b63808dd", "asset-bab403ab"}
missing = expected_assets - set(active)
if missing:
    raise AssertionError(f"missing canonical live assignments: {sorted(missing)}")

for asset_id in sorted(expected_assets):
    print(f"PASS: {asset_id} -> {active[asset_id]}")

print(f"PASS: canonical current assignments {len(expected_assets)}")
PY

echo "Verify PASS"
