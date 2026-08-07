#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
pass(){ echo "PASS: $1"; }
require(){ grep -q "$2" "$1" || { echo "FAIL: $3"; exit 1; }; pass "$3"; }
require frontend/assets.html 'id="fleetSummaryCards"' 'fleet summary dashboard'
require frontend/assets.html 'data-fleet-view="mining"' 'saved operational views'
require frontend/assets.html 'id="fleetQuickFilters"' 'quick filter controls'
require frontend/js/assets.js 'function fleetRecords' 'canonical fleet record builder'
require frontend/js/assets.js 'function fleetRenderGroups' 'collapsible fleet groups'
require frontend/js/assets.js 'fleetVisibleLimit' 'large-fleet incremental rendering'
require frontend/js/assets.js 'function fleetCard' 'operational fleet cards'
require frontend/css/style.css '.fleet-object-grid' 'fleet operations styling'
require frontend/css/style.css '.fleet-card-state-dot' 'operational status indicators'
if command -v node >/dev/null 2>&1; then node --check frontend/js/assets.js; pass 'Fleet JavaScript syntax'; fi
for _ in $(seq 1 15); do
  if curl -fsS http://localhost:8080/assets.html >/tmp/package-068-assets.html 2>/dev/null; then break; fi
  sleep 1
done
grep -q 'fleetSummaryCards' /tmp/package-068-assets.html && pass '/assets.html' || { echo 'FAIL: /assets.html'; exit 1; }
if curl -fsS http://localhost:8080/api/platform/topology >/tmp/package-068-topology.json 2>/dev/null; then
  python3 - <<'PY'
import json
with open('/tmp/package-068-topology.json', encoding='utf-8') as handle:
    data=json.load(handle)
assert isinstance(data.get('nodes'), list), 'topology nodes unavailable'
print(f"PASS: topology fleet objects {len(data['nodes'])}")
PY
else
  echo "FAIL: /api/platform/topology"
  exit 1
fi
echo "Verify PASS"
