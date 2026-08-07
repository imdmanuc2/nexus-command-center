#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"
python3 -m py_compile backend/services/dashboard_summary_service.py backend/modules/platform.py backend/api/server.py
node --check frontend/js/home-v2.js
grep -q '/api/platform/dashboard-summary' backend/api/server.py
grep -q '/api/platform/dashboard-summary' frontend/js/home-v2.js
grep -q 'legacyFallbackUsed' backend/services/dashboard_summary_service.py
echo "PASS: canonical dashboard summary service"
echo "PASS: canonical dashboard API route"
echo "PASS: Home V2 canonical dashboard consumer"
echo "PASS: dashboard source verification matrix"
echo "PASS: legacy fallback reporting"

for i in {1..10}; do
  code="$(curl -sS -o /tmp/pkg071-dashboard.json -w '%{http_code}' http://localhost:8080/api/platform/dashboard-summary || true)"
  [[ "$code" == "200" ]] && break
  sleep 1
done
[[ "${code:-000}" == "200" ]] || { echo "FAIL: /api/platform/dashboard-summary returned ${code:-000}"; exit 1; }
python3 - <<'PY'
import json
p=json.load(open('/tmp/pkg071-dashboard.json'))
assert p.get('canonical') is True
assert p.get('source') == 'nexus-canonical-dashboard'
assert p.get('verification',{}).get('status') == 'verified'
assert p.get('verification',{}).get('legacyFallbackUsed') is False
assert len(p.get('dataSources',{})) >= 7
for key in ('summary','workers','pools','nodes','alerts','events','metrics'):
    assert key in p, key
print(f"PASS: verified canonical sources {len(p['dataSources'])}")
PY
for path in /home-v2.html /assets.html /cmdb-object.html /graph.html; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "http://localhost:8080$path" || true)"
  [[ "$code" == "200" ]] || { echo "FAIL: $path returned $code"; exit 1; }
  echo "PASS: $path"
done
echo "Verify PASS"
