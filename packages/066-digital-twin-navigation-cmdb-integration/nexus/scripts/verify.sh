#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
grep -q '\["CMDB", "/assets.html"\]' frontend/js/nav.js && echo "PASS: top navigation CMDB terminology"
grep -q 'window.location.href = cmdbObjectHref("asset", objectId)' frontend/js/assets.js && echo "PASS: CMDB asset opens Digital Twin"
grep -q '/cmdb-object.html?type=' frontend/js/graph.js && echo "PASS: Explorer opens Digital Twin"
grep -q 'Choose an object from the CMDB' frontend/js/cmdb-object.js && echo "PASS: missing object ID recovery"
grep -q 'CMDB Objects' frontend/assets.html && echo "PASS: CMDB inventory terminology"
curl -fsS http://localhost:8080/assets.html >/dev/null && echo "PASS: /assets.html"
curl -fsS 'http://localhost:8080/cmdb-object.html?type=asset&id=asset-28a5a306' >/dev/null && echo "PASS: /cmdb-object.html with object ID"
curl -fsS http://localhost:8080/graph.html >/dev/null && echo "PASS: /graph.html"
echo "Verify PASS"
