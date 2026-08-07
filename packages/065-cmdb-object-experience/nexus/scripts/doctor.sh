#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"

cd "$REPO_ROOT"
for f in frontend/cmdb-object.html frontend/js/cmdb-object.js frontend/css/cmdb-object.css frontend/css/style.css backend/services/cmdb_object_service.py; do
  test -f "$f" || { echo "FAIL: $f"; exit 1; }
  echo "PASS: $f"
done
for f in payload/frontend/cmdb-object.html payload/frontend/js/cmdb-object.js payload/frontend/css/cmdb-object.css payload/frontend/css/style.css payload/backend/services/cmdb_object_service.py; do
  test -f "$PACKAGE_ROOT/$f" || { echo "FAIL: $f"; exit 1; }
  echo "PASS: $f"
done
echo "Doctor PASS"
