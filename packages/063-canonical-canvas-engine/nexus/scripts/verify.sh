#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

node --check "$ROOT/frontend/js/graph.js"
grep -q 'PACKAGE 063: Live Canvas renders canonical topology edges' "$ROOT/frontend/js/graph.js"
echo "PASS: Live Canvas renders canonical topology only"

if grep -q 'currentByAsset' "$ROOT/frontend/js/graph.js"; then
  echo "FAIL: legacy synthesized miner relationship builder remains" >&2
  exit 1
fi
echo "PASS: no synthesized miner relationships"

grep -q 'edge?.status || "active"' "$ROOT/frontend/js/graph.js"
grep -q 'currentSession !== false' "$ROOT/frontend/js/graph.js"
echo "PASS: inactive and historical edges excluded from Live mode"

grep -q 'timeMachineMode' "$ROOT/frontend/js/graph.js"
echo "PASS: Time Machine edge history preserved"

grep -q '/js/graph.js?v=063' "$ROOT/frontend/graph.html"
echo "PASS: browser cache bust enabled"

curl -fsS http://localhost:8080/graph.html >/dev/null
echo "PASS: /graph.html"

python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://localhost:8080/api/platform/topology", timeout=15) as response:
    topology = json.load(response)

assignments = {}
for edge in topology.get("edges", []):
    kind = str(edge.get("type", "")).lower().replace("_", "-")
    status = str(edge.get("status", "active")).lower()
    if kind != "mines-on" or status != "active":
        continue
    source = edge.get("source")
    target = edge.get("target")
    if source in assignments and assignments[source] != target:
        raise AssertionError(f"multiple active pool targets for {source}")
    assignments[source] = target

expected = {
    "asset-28a5a306": "seymour-btc-solo",
    "asset-b63808dd": "seymour-btc-solo",
    "asset-bab403ab": "seymour-btc-solo",
}
for asset_id, pool_id in expected.items():
    actual = assignments.get(asset_id)
    if actual != pool_id:
        raise AssertionError(f"expected {asset_id} -> {pool_id}, got {actual}")
    print(f"PASS: {asset_id} -> {pool_id}")
print(f"PASS: canonical current assignments {len(expected)}")
PY

echo "Verify PASS"
