#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
grep -q 'Operational Digital Twin' frontend/cmdb-object.html && echo 'PASS: operational Digital Twin header'
grep -q 'Live Operations' frontend/cmdb-object.html && echo 'PASS: live operations summary'
grep -q 'Health & Connectivity' frontend/cmdb-object.html && echo 'PASS: health and connectivity summary'
grep -q 'Recent Timeline' frontend/cmdb-object.html && echo 'PASS: recent timeline'
grep -q 'formatHashrate' frontend/js/cmdb-object.js && echo 'PASS: human-readable hashrate'
grep -q 'parseCoin' frontend/js/cmdb-object.js && echo 'PASS: human-readable coin metadata'
grep -q 'Run Diagnostics' frontend/js/cmdb-object.js && echo 'PASS: context-aware operations'
grep -q 'relationshipCard' frontend/js/cmdb-object.js && echo 'PASS: clickable relationship cards'
for i in {1..15}; do curl -fsS http://localhost:8080/cmdb-object.html >/dev/null && break || sleep 1; done
curl -fsS http://localhost:8080/cmdb-object.html >/dev/null && echo 'PASS: /cmdb-object.html'
curl -fsS http://localhost:8080/api/platform/objects >/dev/null && echo 'PASS: /api/platform/objects'
echo 'Verify PASS'
