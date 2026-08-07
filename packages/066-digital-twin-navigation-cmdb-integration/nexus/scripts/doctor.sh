#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
for f in frontend/assets.html frontend/js/assets.js frontend/js/nav.js frontend/cmdb-object.html frontend/js/cmdb-object.js frontend/js/graph.js; do
  test -f "$f" && echo "PASS: $f" || { echo "FAIL: $f"; exit 1; }
done
for f in payload/frontend/assets.html payload/frontend/js/assets.js payload/frontend/js/nav.js payload/frontend/cmdb-object.html payload/frontend/js/cmdb-object.js payload/frontend/js/graph.js; do
  test -f "$PACKAGE_ROOT/$f" && echo "PASS: $f" || { echo "FAIL: $f"; exit 1; }
done
echo "Doctor PASS"
