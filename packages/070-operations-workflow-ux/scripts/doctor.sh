#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../.." && pwd)"
cd "$REPO_ROOT"
for file in frontend/js/nav.js frontend/css/style.css frontend/home-v2.html frontend/assets.html frontend/graph.html frontend/cmdb-object.html frontend/index.html; do
  test -f "$file" || { echo "FAIL: $file"; exit 1; }
  echo "PASS: $file"
done
node --check "$PACKAGE_ROOT/payload/frontend/js/nav.js" >/dev/null
echo "PASS: Navigation JavaScript syntax"
grep -q 'nexus-workflow-ribbon' "$PACKAGE_ROOT/payload/frontend/css/style.css"
echo "PASS: operator workflow styling"
echo "Doctor PASS"
