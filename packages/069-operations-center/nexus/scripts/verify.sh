#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
grep -q 'Operations Center' frontend/cmdb-object.html && echo 'PASS: embedded Operations Center'
grep -q 'operationCatalog' frontend/js/cmdb-object.js && echo 'PASS: context-aware operation catalog'
grep -q '/api/platform/recommendations' frontend/js/cmdb-object.js && echo 'PASS: object recommendations integration'
grep -q '/api/platform/automation/summary' frontend/js/cmdb-object.js && echo 'PASS: automation evidence integration'
grep -q 'Pool Readiness' frontend/js/cmdb-object.js && echo 'PASS: pool operation actions'
grep -q 'Test RPC' frontend/js/cmdb-object.js && echo 'PASS: blockchain operation actions'
grep -q 'Run Diagnostics' frontend/js/cmdb-object.js && echo 'PASS: miner operation actions'
grep -q 'cmdb-recommendation-card' frontend/css/cmdb-object.css && echo 'PASS: recommendation styling'
node --check frontend/js/cmdb-object.js && echo 'PASS: Operations JavaScript syntax'
for i in {1..10}; do
  if curl -fsS http://localhost:8080/cmdb-object.html >/dev/null 2>&1; then echo 'PASS: /cmdb-object.html'; break; fi
  sleep 1
  test "$i" -lt 10 || { echo 'FAIL: /cmdb-object.html'; exit 1; }
done
curl -fsS http://localhost:8080/api/platform/recommendations >/dev/null && echo 'PASS: /api/platform/recommendations'
curl -fsS http://localhost:8080/api/platform/automation/summary >/dev/null && echo 'PASS: /api/platform/automation/summary'
echo 'Verify PASS'
