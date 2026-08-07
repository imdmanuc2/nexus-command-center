#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"

cd "$REPO_ROOT"
grep -q 'Infrastructure Digital Twin' frontend/cmdb-object.html && echo "PASS: Digital Twin object header"
grep -q 'Current State' frontend/cmdb-object.html && echo "PASS: live operations panel"
grep -q 'Recent Timeline' frontend/cmdb-object.html && echo "PASS: recent timeline panel"
grep -q 'Save Operational Profile' frontend/cmdb-object.html && echo "PASS: operational profile editor"
grep -q 'renderLive' frontend/js/cmdb-object.js && echo "PASS: live telemetry rendering"
grep -q 'renderHealth' frontend/js/cmdb-object.js && echo "PASS: health and connectivity rendering"
grep -q 'renderOperations' frontend/js/cmdb-object.js && echo "PASS: object operations links"
grep -q 'status-accepting-shares' frontend/css/style.css && echo "PASS: green accepting-shares Canvas styling"
curl -fsS http://localhost:8080/cmdb-object.html >/dev/null && echo "PASS: /cmdb-object.html"
curl -fsS http://localhost:8080/api/platform/objects >/dev/null && echo "PASS: /api/platform/objects"
python3 - <<'PY2'
from backend.services.cmdb_object_service import list_objects
p = list_objects()
assert p.get('status') == 'ok'
assert p.get('count', 0) > 0
print(f"PASS: canonical CMDB objects {p['count']}")
PY2
echo "Verify PASS"
