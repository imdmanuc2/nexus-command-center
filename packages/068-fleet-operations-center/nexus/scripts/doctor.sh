#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
check(){ [[ -f "$1" ]] && echo "PASS: $1" || { echo "FAIL: $1"; exit 1; }; }
check frontend/assets.html
check frontend/js/assets.js
check frontend/css/style.css
check "$PACKAGE_ROOT/payload/frontend/assets.html"
check "$PACKAGE_ROOT/payload/frontend/js/assets.js"
check "$PACKAGE_ROOT/payload/frontend/css/style.css"
if command -v node >/dev/null 2>&1; then
  node --check "$PACKAGE_ROOT/payload/frontend/js/assets.js"
  echo "PASS: Fleet JavaScript syntax"
fi
grep -q 'id="fleetSummaryCards"' "$PACKAGE_ROOT/payload/frontend/assets.html" && echo "PASS: fleet summary markup" || { echo "FAIL: fleet summary markup"; exit 1; }
grep -q 'function fleetRenderGroups' "$PACKAGE_ROOT/payload/frontend/js/assets.js" && echo "PASS: scalable fleet grouping" || { echo "FAIL: scalable fleet grouping"; exit 1; }
echo "Doctor PASS"
