#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"
for f in \
 backend/api/server.py \
 backend/modules/platform.py \
 backend/services/home_service.py \
 frontend/home-v2.html \
 frontend/js/home-v2.js \
 "$PACKAGE_ROOT/payload/backend/services/dashboard_summary_service.py" \
 "$PACKAGE_ROOT/payload/backend/modules/platform.py" \
 "$PACKAGE_ROOT/payload/backend/api/server.py" \
 "$PACKAGE_ROOT/payload/frontend/home-v2.html" \
 "$PACKAGE_ROOT/payload/frontend/js/home-v2.js"; do
  [[ -f "$f" ]] && echo "PASS: $f" || { echo "FAIL: $f"; exit 1; }
done
python3 -m py_compile "$PACKAGE_ROOT/payload/backend/services/dashboard_summary_service.py" "$PACKAGE_ROOT/payload/backend/modules/platform.py" "$PACKAGE_ROOT/payload/backend/api/server.py"
node --check "$PACKAGE_ROOT/payload/frontend/js/home-v2.js"
echo "PASS: Python and JavaScript syntax"
echo "Doctor PASS"
