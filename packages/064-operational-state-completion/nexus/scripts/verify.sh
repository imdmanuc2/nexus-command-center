#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

python3 -m py_compile \
  "$ROOT/backend/services/operational_state_engine.py" \
  "$ROOT/backend/services/topology_service.py" \
  "$ROOT/backend/services/seymour_pool_sync_service.py"
node --check "$ROOT/frontend/js/graph.js"

grep -q 'derive_pool_operational_state' "$ROOT/backend/services/operational_state_engine.py"
echo "PASS: canonical pool operational state helper"
grep -q 'pool_state_by_id' "$ROOT/backend/services/topology_service.py"
echo "PASS: topology consumes canonical pool state"
grep -q 'props.observedOperationalState' "$ROOT/frontend/js/graph.js"
echo "PASS: Canvas consumes canonical pool state"

python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://localhost:8080/api/platform/topology", timeout=15) as response:
    topology = json.load(response)

pool = next((node for node in topology.get("nodes", []) if node.get("id") == "seymour-btc-solo"), None)
assert pool, "Seymour pool node missing"
props = pool.get("properties") or {}
state = str(pool.get("status") or props.get("observedOperationalState") or "")
workers = int(props.get("onlineWorkerCount") or (props.get("observedState") or {}).get("activeWorkers") or 0)
hashrate = float(props.get("currentHashrate") or (props.get("observedState") or {}).get("hashrate") or 0)
assert state == "accepting-shares", f"expected accepting-shares, got {state}"
assert workers >= 1, f"expected active workers, got {workers}"
assert hashrate > 0, f"expected positive pool hashrate, got {hashrate}"
print(f"PASS: Seymour pool state {state}")
print(f"PASS: Seymour active workers {workers}")
print(f"PASS: Seymour pool hashrate {hashrate}")
PY

curl -fsS http://localhost:8080/graph.html >/dev/null
echo "PASS: /graph.html"
echo "Verify PASS"
