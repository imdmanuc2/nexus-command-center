#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
for f in frontend/cmdb-object.html frontend/js/cmdb-object.js frontend/css/cmdb-object.css; do
  test -f "$f" || { echo "FAIL: $f"; exit 1; }
  echo "PASS: $f"
done
for f in "$PACKAGE_ROOT/payload/frontend/cmdb-object.html" "$PACKAGE_ROOT/payload/frontend/js/cmdb-object.js" "$PACKAGE_ROOT/payload/frontend/css/cmdb-object.css"; do
  test -f "$f" || { echo "FAIL: $f"; exit 1; }
  echo "PASS: $f"
done
node --check "$PACKAGE_ROOT/payload/frontend/js/cmdb-object.js"
grep -q 'Operations Center' "$PACKAGE_ROOT/payload/frontend/cmdb-object.html"
grep -q 'loadOperationsCenter' "$PACKAGE_ROOT/payload/frontend/js/cmdb-object.js"
grep -q 'cmdb-recommendation-card' "$PACKAGE_ROOT/payload/frontend/css/cmdb-object.css"
echo "Doctor PASS"
