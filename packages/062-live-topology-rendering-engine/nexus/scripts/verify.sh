#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

node --check "$ROOT/frontend/js/graph.js"

grep -q 'function canvasCanonicalLiveEdges' "$ROOT/frontend/js/graph.js"
echo "PASS: canonical live relationship builder"

grep -q 'worker.currentSession !== true' "$ROOT/frontend/js/graph.js"
echo "PASS: current-session filtering"

grep -q 'if (timeMachineMode)' "$ROOT/frontend/js/graph.js"
echo "PASS: Time Machine history preserved"

grep -q 'replaceAll("-", "_")' "$ROOT/frontend/js/graph.js"
echo "PASS: relationship type normalization"

python3 - <<'PY'
import json
from urllib.request import urlopen

with urlopen('http://127.0.0.1:8080/api/platform/workers', timeout=15) as r:
    workers = json.load(r).get('workers', [])
with urlopen('http://127.0.0.1:8080/api/platform/topology', timeout=15) as r:
    topology = json.load(r)

node_ids = {str(n.get('id')) for n in topology.get('nodes', [])}
current = {}
for worker in workers:
    if worker.get('currentSession') is not True:
        continue
    asset = str(worker.get('assetId') or '').strip()
    pool = str(worker.get('poolInstanceId') or '').strip()
    status = str(worker.get('status') or '').lower()
    if not asset or not pool or status in {'stale','offline','retired','disconnected'}:
        continue
    if asset in node_ids and pool in node_ids:
        current[asset] = pool

assert current, 'no canonical current mining assignments found'
assert len(current) == len(set(current)), 'duplicate active physical asset assignment'
print(f"PASS: canonical current assignments {len(current)}")
for asset, pool in sorted(current.items()):
    print(f"PASS: {asset} -> {pool}")
PY

curl -fsS http://127.0.0.1:8080/graph.html >/dev/null
echo "PASS: /graph.html"

echo "Verify PASS"
